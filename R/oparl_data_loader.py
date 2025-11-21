"""
OParl Data Loader für Augsburg Stadtrat
========================================

Dieses Modul lädt Daten von der Augsburg OParl API und cached sie lokal.
Kann als importierbare Funktion in Notebooks genutzt werden.

Verwendung:
    from R.oparl_data_loader import load_augsburg_data

    df_meetings, df_locations = load_augsburg_data(
        date_from='2020-01-01',
        date_to='2025-11-20',
        load_papers=True,
        geocode_locations=True
    )
"""

import requests
import pandas as pd
import time
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re

# Import Smart Location Extractor
try:
    import sys
    import os as _os
    # Add R directory to path if this file is in R/
    _current_dir = _os.path.dirname(_os.path.abspath(__file__))
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
    from location_extractor import AugsburgLocationExtractor
    _USE_SMART_EXTRACTOR = True
except ImportError as e:
    print(f"⚠️  location_extractor.py nicht gefunden - nutze alte Regex ({e})")
    _USE_SMART_EXTRACTOR = False

# Globale Konfiguration
OPARL_SYSTEM_URL = "https://www.augsburg.sitzung-online.de/public/oparl/system"
CACHE_DIR = "data-raw"

# Globale Caches
_MEETING_ENDPOINT_CACHE = None
_ORG_NAME_CACHE = {}
_LOCATION_EXTRACTOR = None  # Wird bei Bedarf initialisiert


def get_meeting_endpoint():
    """
    Navigiert durch die OParl-Struktur: System -> Bodies -> Body -> Meeting-Endpoint
    """
    global _MEETING_ENDPOINT_CACHE

    if _MEETING_ENDPOINT_CACHE:
        return _MEETING_ENDPOINT_CACHE

    # Hole System-Objekt
    system_response = requests.get(OPARL_SYSTEM_URL, timeout=10)
    system_data = system_response.json()

    # Extrahiere Bodies-List-URL
    bodies_url = system_data.get('body')
    if isinstance(bodies_url, list):
        bodies_url = bodies_url[0] if bodies_url else None

    if not bodies_url:
        raise ValueError("Keine Body-URL gefunden!")

    # Hole Bodies-Liste
    bodies_response = requests.get(bodies_url, timeout=10)
    bodies_data = bodies_response.json()

    # Extrahiere das erste Body-Objekt
    bodies_list = bodies_data.get('data', [])
    if not bodies_list:
        raise ValueError("Keine Bodies in der Liste gefunden!")

    body_id = bodies_list[0].get('id')
    print(f"✓ Body gefunden: {bodies_list[0].get('name', 'Unbenannt')}")

    # Hole vollständiges Body-Objekt
    body_response = requests.get(body_id, timeout=10)
    body_data = body_response.json()

    meeting_url = body_data.get('meeting')
    _MEETING_ENDPOINT_CACHE = meeting_url

    return meeting_url


def get_body_data():
    """
    Holt das vollständige Body-Objekt mit allen Endpunkten
    """
    system_response = requests.get(OPARL_SYSTEM_URL, timeout=10)
    system_data = system_response.json()

    bodies_url = system_data.get('body')
    if isinstance(bodies_url, list):
        bodies_url = bodies_url[0]

    bodies_response = requests.get(bodies_url, timeout=10)
    bodies_data = bodies_response.json()
    bodies_list = bodies_data.get('data', [])

    body_id = bodies_list[0].get('id')
    body_response = requests.get(body_id, timeout=10)

    return body_response.json()


def fetch_meetings_fast(limit_pages=50, cache_file=None):
    """
    Lädt Meetings mit Threading + lokalem Cache
    """
    if cache_file is None:
        cache_file = os.path.join(CACHE_DIR, 'augsburg_meetings_cache.parquet')

    # Prüfe Cache
    if os.path.exists(cache_file):
        print(f"📦 Lade Daten aus Cache: {cache_file}")
        df = pd.read_parquet(cache_file)
        print(f"✓ {len(df)} Sitzungen aus Cache geladen")
        return df

    print(f"🌐 Kein Cache gefunden - lade von API mit Threading...")

    # Sammle Seiten-URLs
    url = get_meeting_endpoint()
    if not url:
        return pd.DataFrame()

    page_urls = []
    page_count = 0

    print("📋 Sammle Seiten-URLs...")
    while url and page_count < limit_pages:
        page_urls.append(url)
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            links = data.get('links', {})
            url = links.get('next')
            page_count += 1
            if page_count % 10 == 0:
                print(f"   {page_count} URLs gesammelt...")
        except Exception as e:
            print(f"⚠️ Fehler beim URL-Sammeln: {e}")
            break

    print(f"✓ {len(page_urls)} Seiten-URLs gesammelt.\n")

    # Paralleles Laden
    def fetch_page(url):
        try:
            response = requests.get(url, timeout=15)
            response.raise_for_status()
            data = response.json()
            items = data.get('data', [])

            meetings = []
            for item in items:
                meetings.append({
                    'name': item.get('name', 'Unbenannte Sitzung'),
                    'start': item.get('start'),
                    'end': item.get('end'),
                    'organization': item.get('organization', ['Unknown'])[0] if item.get('organization') else 'Unknown'
                })
            return meetings
        except Exception as e:
            print(f"⚠️ Fehler bei Seite: {e}")
            return []

    print("⚡ Lade Seiten parallel (bis zu 10 gleichzeitig)...")
    all_meetings = []

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_page, url): i for i, url in enumerate(page_urls)}

        for future in as_completed(futures):
            page_num = futures[future]
            meetings = future.result()
            all_meetings.extend(meetings)
            print(f"  ✓ Seite {page_num + 1}/{len(page_urls)}: {len(meetings)} Meetings (Total: {len(all_meetings)})")

    print(f"\n✓ {len(all_meetings)} Sitzungen geladen!\n")

    # In DataFrame konvertieren
    df = pd.DataFrame(all_meetings)

    # Cache speichern
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    df.to_parquet(cache_file)
    print(f"💾 Cache gespeichert: {cache_file}\n")

    return df


def get_organization_name(org_url):
    """
    Holt den Namen einer Organisation von ihrer URL
    """
    if not org_url or org_url == 'Unknown':
        return 'Unbekannt'

    if org_url in _ORG_NAME_CACHE:
        return _ORG_NAME_CACHE[org_url]

    try:
        response = requests.get(org_url, timeout=10)
        response.raise_for_status()
        org_data = response.json()
        name = org_data.get('name', org_url)
        _ORG_NAME_CACHE[org_url] = name
        return name
    except Exception:
        _ORG_NAME_CACHE[org_url] = org_url
        return org_url


def enrich_organization_names(df):
    """
    Fügt Organisationsnamen hinzu
    """
    print("🔄 Lade Organisationsnamen...")

    unique_orgs = df['organization'].unique()
    print(f"   {len(unique_orgs)} verschiedene Organisationen")

    org_names = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(get_organization_name, url): url for url in unique_orgs}

        for future in as_completed(futures):
            url = futures[future]
            name = future.result()
            org_names[url] = name
            if len(org_names) % 5 == 0:
                print(f"   {len(org_names)}/{len(unique_orgs)} geladen...")

    df['organization_name'] = df['organization'].map(org_names)
    print(f"✓ Organisationsnamen geladen!\n")

    return df


def get_location_extractor():
    """Lazy loading des Smart Extractors"""
    global _LOCATION_EXTRACTOR
    if _LOCATION_EXTRACTOR is None and _USE_SMART_EXTRACTOR:
        print("🤖 Initialisiere Smart Location Extractor...")
        _LOCATION_EXTRACTOR = AugsburgLocationExtractor()
    return _LOCATION_EXTRACTOR


def extract_location(text):
    """
    Extrahiert Straßennamen und Ortsnamen aus Text.
    Nutzt Smart Extractor falls verfügbar, sonst Regex.
    Returns: Liste von Locations (kann leer sein)
    """
    if not isinstance(text, str) or not text:
        return []

    # Versuche Smart Extractor
    extractor = get_location_extractor()
    if extractor:
        return extractor.get_locations_from_text(text)

    # Fallback: Alte Regex-Methode
    results = []

    # Muster 1: Text in Anführungszeichen
    match_quotes = re.search(r"[‚'„](.*?)[''""]", text)
    if match_quotes:
        extracted = match_quotes.group(1)
        if re.search(r'(straße|platz|allee|weg|gasse|ring|pfad)$', extracted.lower()):
            results.append(extracted)

    # Muster 2: Direktsuche nach Straßennamen
    match_street = re.search(r'([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)*(?:straße|platz|allee|weg|gasse|ring|pfad))', text)
    if match_street:
        loc = match_street.group(1)
        if loc not in results:
            results.append(loc)

    # Muster 3: Stadtteile/Bezirke
    match_district = re.search(r'(?:in|im Bereich|im Stadtteil)\s+([A-ZÄÖÜ][a-zäöüß\-]+(?:\s+[A-ZÄÖÜ][a-zäöüß\-]+)?)', text)
    if match_district:
        loc = match_district.group(1)
        if loc not in results:
            results.append(loc)

    return results


def load_papers_with_locations(max_pages=10):
    """
    Lädt Papers und extrahiert Ortsangaben
    """
    print("📄 LADE PAPERS MIT ORTSANGABEN\n")

    body_data = get_body_data()

    def fetch_paper_page(url):
        try:
            response = requests.get(url, timeout=15)
            data = response.json()
            papers = data.get('data', [])
            next_url = data.get('links', {}).get('next')
            return papers, next_url
        except Exception as e:
            print(f"⚠️ Fehler: {e}")
            return [], None

    # Sammle Seiten-URLs
    paper_url = body_data['paper']
    page_urls = []
    current = paper_url
    page = 1

    print("📋 Sammle Paper-Seiten...")
    while current and page <= max_pages:
        page_urls.append(current)
        _, next_url = fetch_paper_page(current)
        current = next_url
        page += 1

    print(f"✓ {len(page_urls)} Seiten zum Laden\n")

    # Lade parallel
    all_papers = []
    print("⚡ Lade Papers parallel...")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_paper_page, url): i for i, url in enumerate(page_urls)}

        for future in as_completed(futures):
            page_num = futures[future]
            papers, _ = future.result()
            all_papers.extend(papers)

    print(f"\n✓ {len(all_papers)} Papers geladen!\n")

    # Extrahiere Ortsangaben mit Smart Extractor
    print("🗺️  EXTRAHIERE ORTSANGABEN...\n")

    locations_in_papers = []
    for paper in all_papers:
        name = paper.get('name', '')
        locations = extract_location(name)  # Jetzt gibt's Liste zurück!

        # Jede gefundene Location als separate Zeile
        for location in locations:
            locations_in_papers.append({
                'location': location,
                'paper_name': name,
                'paper_id': paper.get('id'),
                'date': paper.get('date'),
                'type': paper.get('paperType', 'Unbekannt')
            })

    df_locations = pd.DataFrame(locations_in_papers)

    if not df_locations.empty:
        print(f"📊 {len(df_locations)} Ortsangaben in {len(all_papers)} Papers gefunden")
        print(f"   Das sind {len(df_locations)/len(all_papers)*100:.1f}% der Papers")

        # Zeige Statistik
        unique_locations = df_locations['location'].nunique()
        print(f"   {unique_locations} eindeutige Orte")

        if _USE_SMART_EXTRACTOR:
            print(f"   ✅ Smart Extractor (NER + OSM) verwendet\n")
        else:
            print(f"   ⚠️  Fallback Regex verwendet\n")
    else:
        print(f"⚠️  Keine Ortsangaben in {len(all_papers)} Papers gefunden\n")

    return df_locations


def geocode_locations(df_locations, max_locations=20):
    """
    Geocodiert die gefundenen Orte mit Nominatim
    """
    from geopy.geocoders import Nominatim

    print(f"🌍 GEOCODING VON {min(len(df_locations), max_locations)} ORTEN\n")

    # Filter: Ohne "Augsburg"
    specific = df_locations[~df_locations['location'].isin(['Augsburg'])].copy()
    unique_locations = specific['location'].unique()[:max_locations]

    geolocator = Nominatim(user_agent="augsburg_papers_geocoding_2025")
    geocoded = []

    for i, location in enumerate(unique_locations, 1):
        query = f"{location}, Augsburg, Germany"

        try:
            result = geolocator.geocode(query)

            if result:
                geocoded.append({
                    'location': location,
                    'lat': result.latitude,
                    'lon': result.longitude,
                    'full_address': result.address,
                    'success': True
                })
                print(f"✅ {i}/{len(unique_locations)} {location}")
            else:
                geocoded.append({
                    'location': location,
                    'lat': None,
                    'lon': None,
                    'full_address': None,
                    'success': False
                })
                print(f"❌ {i}/{len(unique_locations)} {location}")

            time.sleep(1.1)  # Rate limit

        except Exception as e:
            print(f"⚠️ {i}/{len(unique_locations)} {location} - Fehler: {e}")
            geocoded.append({
                'location': location,
                'lat': None,
                'lon': None,
                'full_address': None,
                'success': False
            })
            time.sleep(1.1)

    df_geocoded = pd.DataFrame(geocoded)
    successful = df_geocoded[df_geocoded['success'] == True]

    print(f"\n✅ {len(successful)}/{len(df_geocoded)} Orte erfolgreich geocoded ({len(successful)/len(df_geocoded)*100:.1f}%)\n")

    return df_geocoded


def load_augsburg_data(
    date_from='2020-01-01',
    date_to='2025-11-20',
    load_papers=True,
    geocode_locations_flag=False,
    max_paper_pages=10,
    max_meeting_pages=50
):
    """
    Hauptfunktion: Lädt alle Augsburg Daten

    Args:
        date_from: Start-Datum für Filterung
        date_to: End-Datum für Filterung
        load_papers: Papers mit Ortsangaben laden?
        geocode_locations_flag: Orte geocodieren?
        max_paper_pages: Maximale Anzahl Paper-Seiten
        max_meeting_pages: Maximale Anzahl Meeting-Seiten

    Returns:
        tuple: (df_meetings, df_locations, df_geocoded) oder (df_meetings, None, None)
    """
    print("="*60)
    print("AUGSBURG OPARL DATA LOADER")
    print("="*60)
    print(f"Zeitraum: {date_from} bis {date_to}\n")

    # 1. Lade Meetings
    df = fetch_meetings_fast(limit_pages=max_meeting_pages)

    # 2. Verarbeite Meetings
    if not df.empty:
        df['start'] = pd.to_datetime(df['start'], utc=True)
        df['end'] = pd.to_datetime(df['end'], utc=True)
        df['start_local'] = df['start'].dt.tz_convert('Europe/Berlin')
        df['weekday'] = df['start_local'].dt.day_name()
        df['hour'] = df['start_local'].dt.hour

        # Organisationsnamen
        df = enrich_organization_names(df)

        # Datum-Filterung
        df_clean = df.dropna(subset=['start'])
        df_clean = df_clean[
            (df_clean['start_local'] >= pd.Timestamp(date_from, tz='Europe/Berlin')) &
            (df_clean['start_local'] <= pd.Timestamp(date_to, tz='Europe/Berlin'))
        ].copy()

        print(f"✓ {len(df_clean)} Meetings nach Filterung ({date_from} - {date_to})\n")
    else:
        df_clean = pd.DataFrame()

    # 3. Lade Papers (optional)
    if load_papers and not df_clean.empty:
        df_locations = load_papers_with_locations(max_pages=max_paper_pages)

        # 4. Geocode (optional)
        if geocode_locations_flag and not df_locations.empty:
            df_geocoded = geocode_locations(df_locations)
            return df_clean, df_locations, df_geocoded

        return df_clean, df_locations, None

    return df_clean, None, None


if __name__ == "__main__":
    # Beispiel-Verwendung
    print("Lade Augsburg Daten...\n")

    df_meetings, df_locations, df_geocoded = load_augsburg_data(
        date_from='2020-01-01',
        date_to='2025-11-20',
        load_papers=True,
        geocode_locations_flag=True,
        max_paper_pages=10
    )

    print("\n" + "="*60)
    print("ZUSAMMENFASSUNG")
    print("="*60)
    print(f"Meetings: {len(df_meetings)}")
    if df_locations is not None:
        print(f"Papers mit Ortsangaben: {len(df_locations)}")
    if df_geocoded is not None:
        successful = df_geocoded[df_geocoded['success'] == True]
        print(f"Geocodierte Orte: {len(successful)}/{len(df_geocoded)}")
