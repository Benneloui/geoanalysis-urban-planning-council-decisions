import os
import time
import requests
import pandas as pd
import logging
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime

# Bibliotheken für PDF und RDF
# pip install pypdf rdflib pandas requests pyarrow
from pypdf import PdfReader
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, XSD

# --- KONFIGURATION ---
BASE_URL = "https://www.augsburg.sitzung-online.de/public/oparl/body/1/paper"
START_DATE = "2023-01-01T00:00:00"  # Augsburg scheint ab 2023 Daten zu haben
DATA_DIR = Path("data")
PDF_DIR = DATA_DIR / "pdfs"
OUTPUT_PARQUET = DATA_DIR / "augsburg_papers.parquet"
OUTPUT_TTL = DATA_DIR / "augsburg_metadata.ttl"

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Ordner erstellen
PDF_DIR.mkdir(parents=True, exist_ok=True)

# --- ROBUSTE API SESSION ---
def get_session():
    session = requests.Session()
    retry = Retry(connect=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

session = get_session()

# --- SCHRITT 1: METADATEN LADEN ---
def fetch_papers_metadata():
    """Lädt alle Paper-Objekte seit START_DATE über die Pagination."""
    papers = []
    url = f"{BASE_URL}?modified_since={START_DATE}"

    logger.info("Starte Download der Metadaten...")

    while url:
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            # Daten extrahieren
            items = data.get('data', [])
            papers.extend(items)
            logger.info(f"{len(items)} Papers geladen (Total: {len(papers)})")

            # Pagination
            links = data.get('links', {})
            url = links.get('next')

            # API nicht überlasten
            time.sleep(0.5)

        except Exception as e:
            logger.error(f"Fehler beim Abruf von {url}: {e}")
            break

    return papers

# --- SCHRITT 2 & 3: PDF DOWNLOAD & EXTRAKTION ---
def process_pdf(paper):
    """Lädt PDF herunter (falls nicht vorhanden) und extrahiert Text."""
    paper_id = paper.get('id')
    # Sicheren Dateinamen aus ID generieren
    safe_id = paper_id.split('/')[-1]
    pdf_path = PDF_DIR / f"{safe_id}.pdf"

    # URL finden (mainFile oder erstes file)
    pdf_url = None
    if 'mainFile' in paper and isinstance(paper['mainFile'], dict):
        pdf_url = paper['mainFile'].get('accessUrl')
    elif 'file' in paper and isinstance(paper['file'], list) and len(paper['file']) > 0:
        pdf_url = paper['file'][0].get('accessUrl')

    if not pdf_url:
        return None, None  # Kein PDF

    # 2. Download (Cache prüfen)
    if not pdf_path.exists():
        try:
            logger.info(f"Downloade PDF: {safe_id}")
            resp = session.get(pdf_url, stream=True, timeout=60)
            if resp.status_code == 200:
                with open(pdf_path, 'wb') as f:
                    for chunk in resp.iter_content(chunk_size=8192):
                        f.write(chunk)
                time.sleep(1) # Pause für den Server
            else:
                logger.warning(f"Konnte PDF nicht laden: {resp.status_code}")
                return None, pdf_url
        except Exception as e:
            logger.error(f"Download Fehler {safe_id}: {e}")
            return None, pdf_url

    # 3. Text Extraktion (Lokal)
    text_content = ""
    try:
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text_content += extracted + "\n"
    except Exception as e:
        logger.warning(f"PDF unlesbar {safe_id}: {e}")
        return None, pdf_url

    return text_content, pdf_url

# --- HAUPTPROGRAMM ---
def main():
    # 1. Metadaten holen
    papers_meta = fetch_papers_metadata()
    logger.info(f"Metadaten komplett. Verarbeite {len(papers_meta)} Einträge...")

    processed_data = []

    # 2. Loop über Papers
    for i, paper in enumerate(papers_meta):
        if i % 10 == 0:
            logger.info(f"Verarbeite Paper {i}/{len(papers_meta)}")

        full_text, pdf_url = process_pdf(paper)

        # Datensatz erstellen
        entry = {
            "id": paper.get('id'),
            "name": paper.get('name'),
            "reference": paper.get('reference'),
            "date": paper.get('date'),
            "type": paper.get('paperType'),
            "pdf_url": pdf_url,
            "full_text": full_text # Hier ist der Inhalt für Parquet
        }
        processed_data.append(entry)

    # DataFrame erstellen
    df = pd.DataFrame(processed_data)

    # --- SCHRITT 4A: SPEICHERN ALS PARQUET ---
    logger.info(f"Speichere {len(df)} Zeilen nach {OUTPUT_PARQUET}")
    # Konvertiere ID zu String, falls nötig, für Parquet Kompatibilität
    df = df.astype({"id": "string", "full_text": "string"})
    df.to_parquet(OUTPUT_PARQUET)

    # --- SCHRITT 4B: RDF EXPORT ---
    logger.info("Generiere RDF Graph...")
    g = Graph()
    OPARL = Namespace("http://oparl.org/schema/1.0/")
    GEO = Namespace("http://www.opengis.net/ont/geosparql#")
    EX = Namespace("http://example.org/augsburg/")

    g.bind("oparl", OPARL)
    g.bind("geo", GEO)

    for _, row in df.iterrows():
        if not row['id']: continue

        paper_uri = URIRef(row['id'])

        # Basis-Triples
        g.add((paper_uri, RDF.type, OPARL.Paper))
        if row['name']:
            g.add((paper_uri, OPARL.name, Literal(row['name'])))
        if row['reference']:
            g.add((paper_uri, OPARL.reference, Literal(row['reference'])))
        if row['date']:
            g.add((paper_uri, OPARL.date, Literal(row['date'], datatype=XSD.date)))

        # Hier später: Geo-Referenzierung aus Schritt 3 hinzufügen
        # if row['geo_wkt']:
        #     g.add((paper_uri, GEO.hasGeometry, Literal(row['geo_wkt'], datatype=GEO.wktLiteral)))

    logger.info(f"Speichere RDF nach {OUTPUT_TTL}")
    g.serialize(destination=OUTPUT_TTL, format="turtle")

    logger.info("Fertig! 🎉")

if __name__ == "__main__":
    main()