"""
ETL-Pipeline für Stadtratssitzungs-HTML-Dumps zu PostgreSQL

Dieses Skript extrahiert Daten aus HTML-Dumps, reichert sie mit NER und Geocoding an,
und lädt sie in eine PostgreSQL/PostGIS-Datenbank.

Abhängigkeiten:
    pip install beautifulsoup4 lxml psycopg2-binary sqlalchemy geoalchemy2 \
                spacy geopy pandas python-dateutil
    python -m spacy download de_core_news_lg
"""

import os
import re
import uuid
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

# HTML Parsing
from bs4 import BeautifulSoup
import lxml

# Database
import psycopg2
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
import pandas as pd

# NLP & Geocoding
import spacy
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import time

# Utilities
from dateutil import parser as date_parser

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== DATA MODELS ====================

@dataclass
class Organization:
    """Datenmodell für Gremium/Fraktion"""
    name: str
    organization_type: str
    short_name: Optional[str] = None
    description: Optional[str] = None
    website: Optional[str] = None
    source_url: Optional[str] = None
    id: Optional[uuid.UUID] = None
    
    def to_dict(self):
        data = asdict(self)
        if data['id']:
            data['id'] = str(data['id'])
        return data


@dataclass
class Person:
    """Datenmodell für Person/Mandatsträger"""
    family_name: str
    given_name: Optional[str] = None
    academic_title: Optional[str] = None
    form_of_address: Optional[str] = None
    email: Optional[str] = None
    source_url: Optional[str] = None
    id: Optional[uuid.UUID] = None
    
    def to_dict(self):
        data = asdict(self)
        if data['id']:
            data['id'] = str(data['id'])
        return data


@dataclass
class Meeting:
    """Datenmodell für Sitzung"""
    name: str
    start_time: Optional[datetime] = None
    organization_id: Optional[uuid.UUID] = None
    meeting_type: str = 'public'
    location: Optional[str] = None
    location_lat: Optional[float] = None
    location_lon: Optional[float] = None
    meeting_status: str = 'held'
    source_url: Optional[str] = None
    source_html_path: Optional[str] = None
    id: Optional[uuid.UUID] = None


@dataclass
class AgendaItem:
    """Datenmodell für Tagesordnungspunkt"""
    meeting_id: uuid.UUID
    title: str
    number: Optional[str] = None
    description: Optional[str] = None
    position: Optional[int] = None
    result: Optional[str] = None
    source_url: Optional[str] = None
    id: Optional[uuid.UUID] = None


@dataclass
class Paper:
    """Datenmodell für Vorlage/Drucksache"""
    name: str
    reference: Optional[str] = None
    paper_type: str = 'Vorlage'
    abstract: Optional[str] = None
    full_text: Optional[str] = None
    date_published: Optional[datetime] = None
    mentioned_locations: Optional[List[str]] = None
    source_url: Optional[str] = None
    id: Optional[uuid.UUID] = None


@dataclass
class Document:
    """Datenmodell für Dokument/Datei"""
    filename: str
    title: Optional[str] = None
    mime_type: Optional[str] = None
    file_path: Optional[str] = None
    extracted_text: Optional[str] = None
    document_type: str = 'unknown'
    extracted_addresses: Optional[List[Dict]] = None
    source_url: Optional[str] = None
    download_url: Optional[str] = None
    id: Optional[uuid.UUID] = None


# ==================== EXTRACTORS ====================

class HTMLExtractor:
    """Extrahiert strukturierte Daten aus HTML-Dumps"""
    
    def __init__(self, html_dir: str):
        self.html_dir = Path(html_dir)
        self.logger = logging.getLogger(self.__class__.__name__)
    
    def extract_meeting_from_html(self, html_path: Path) -> Optional[Meeting]:
        """
        Extrahiert Meeting-Daten aus HTML-Datei.
        
        Diese Methode muss an die spezifische HTML-Struktur angepasst werden!
        """
        self.logger.info(f"Parsing: {html_path}")
        
        try:
            with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                soup = BeautifulSoup(f.read(), 'lxml')
            
            # BEISPIEL - MUSS ANGEPASST WERDEN an tatsächliche HTML-Struktur!
            
            # Meeting Name aus Title oder H1
            name = None
            if soup.title:
                name = soup.title.string
            elif soup.find('h1'):
                name = soup.find('h1').get_text(strip=True)
            
            if not name:
                self.logger.warning(f"Kein Meeting-Name gefunden in {html_path}")
                return None
            
            # Datum extrahieren (verschiedene Patterns probieren)
            start_time = self._extract_date(soup)
            
            # Ort extrahieren
            location = self._extract_location(soup)
            
            # Gremium/Organisation
            organization_name = self._extract_organization(soup)
            
            meeting = Meeting(
                name=name,
                start_time=start_time,
                location=location,
                source_html_path=str(html_path),
                source_url=self._extract_source_url(soup)
            )
            
            return meeting
            
        except Exception as e:
            self.logger.error(f"Fehler beim Parsen von {html_path}: {e}")
            return None
    
    def _extract_date(self, soup: BeautifulSoup) -> Optional[datetime]:
        """Extrahiert Datum aus HTML"""
        
        # Suche nach verschiedenen Datumsformaten
        date_patterns = [
            r'\d{2}\.\d{2}\.\d{4}',  # 15.03.2024
            r'\d{1,2}\.\s*\w+\s*\d{4}',  # 15. März 2024
            r'\d{4}-\d{2}-\d{2}',  # 2024-03-15
        ]
        
        # Durchsuche relevante Tags
        for tag in soup.find_all(['div', 'span', 'p', 'td'], class_=re.compile(r'date|datum|zeit', re.I)):
            text = tag.get_text()
            for pattern in date_patterns:
                match = re.search(pattern, text)
                if match:
                    try:
                        # Versuche zu parsen
                        return date_parser.parse(match.group(), dayfirst=True, fuzzy=True)
                    except:
                        continue
        
        return None
    
    def _extract_location(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Ort aus HTML"""
        
        # Suche nach Orts-Informationen
        for tag in soup.find_all(['div', 'span', 'p', 'td'], class_=re.compile(r'ort|location|raum', re.I)):
            text = tag.get_text(strip=True)
            if len(text) > 3 and len(text) < 200:
                return text
        
        return None
    
    def _extract_organization(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Gremium aus HTML"""
        
        for tag in soup.find_all(['div', 'span', 'h2', 'h3'], class_=re.compile(r'gremium|organization', re.I)):
            text = tag.get_text(strip=True)
            if len(text) > 3 and len(text) < 200:
                return text
        
        return None
    
    def _extract_source_url(self, soup: BeautifulSoup) -> Optional[str]:
        """Extrahiert Original-URL wenn vorhanden"""
        
        # Suche nach canonical URL
        canonical = soup.find('link', rel='canonical')
        if canonical and canonical.get('href'):
            return canonical['href']
        
        return None
    
    def extract_agenda_items(self, soup: BeautifulSoup, meeting_id: uuid.UUID) -> List[AgendaItem]:
        """Extrahiert Tagesordnungspunkte aus HTML"""
        
        items = []
        
        # BEISPIEL - ANPASSEN an HTML-Struktur
        # Suche nach Tabellen oder Listen mit Tagesordnung
        
        # Variante 1: Tabelle
        table = soup.find('table', class_=re.compile(r'tagesordnung|agenda', re.I))
        if table:
            for idx, row in enumerate(table.find_all('tr')[1:], 1):  # Skip header
                cells = row.find_all('td')
                if len(cells) >= 2:
                    number = cells[0].get_text(strip=True)
                    title = cells[1].get_text(strip=True)
                    
                    if title:
                        items.append(AgendaItem(
                            meeting_id=meeting_id,
                            number=number,
                            title=title,
                            position=idx
                        ))
        
        # Variante 2: Nummerierte Liste
        for ol in soup.find_all('ol', class_=re.compile(r'tagesordnung|agenda', re.I)):
            for idx, li in enumerate(ol.find_all('li'), 1):
                title = li.get_text(strip=True)
                if title:
                    items.append(AgendaItem(
                        meeting_id=meeting_id,
                        number=str(idx),
                        title=title,
                        position=idx
                    ))
        
        return items
    
    def extract_all_meetings(self) -> List[Tuple[Meeting, List[AgendaItem]]]:
        """Extrahiert alle Meetings aus HTML-Verzeichnis"""
        
        results = []
        
        # Finde alle HTML-Dateien
        html_files = list(self.html_dir.rglob('*.html')) + list(self.html_dir.rglob('*.htm'))
        
        self.logger.info(f"Gefunden: {len(html_files)} HTML-Dateien")
        
        for html_file in html_files:
            meeting = self.extract_meeting_from_html(html_file)
            
            if meeting:
                # Lade HTML nochmal für Agenda Items
                with open(html_file, 'r', encoding='utf-8', errors='ignore') as f:
                    soup = BeautifulSoup(f.read(), 'lxml')
                
                meeting.id = uuid.uuid4()
                agenda_items = self.extract_agenda_items(soup, meeting.id)
                
                results.append((meeting, agenda_items))
        
        self.logger.info(f"Extrahiert: {len(results)} Meetings")
        return results


# ==================== TRANSFORMERS ====================

class DataTransformer:
    """Reichert Daten an mit NER, Geocoding, etc."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # spaCy NER Modell
        try:
            self.nlp = spacy.load("de_core_news_lg")
            self.logger.info("spaCy Modell geladen")
        except:
            self.logger.warning("spaCy Modell nicht verfügbar - NER deaktiviert")
            self.nlp = None
        
        # Geocoder
        self.geocoder = Nominatim(user_agent="stadtrat_etl_pipeline")
    
    def enrich_meeting_with_geocoding(self, meeting: Meeting, city: str = "Deutschland") -> Meeting:
        """Geocodiert Meeting-Location"""
        
        if not meeting.location:
            return meeting
        
        try:
            # Versuche zu geocodieren
            query = f"{meeting.location}, {city}"
            location = self.geocoder.geocode(query, timeout=10)
            
            if location:
                meeting.location_lat = location.latitude
                meeting.location_lon = location.longitude
                self.logger.info(f"Geocoded: {meeting.location} -> {location.latitude}, {location.longitude}")
            else:
                self.logger.warning(f"Geocoding fehlgeschlagen für: {meeting.location}")
            
            # Rate limiting
            time.sleep(1)
            
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            self.logger.error(f"Geocoding Error: {e}")
        
        return meeting
    
    def extract_entities_from_text(self, text: str) -> Dict:
        """Extrahiert Named Entities mit spaCy"""
        
        if not self.nlp or not text:
            return {
                'persons': [],
                'organizations': [],
                'locations': [],
                'dates': [],
                'amounts': []
            }
        
        doc = self.nlp(text[:10000])  # Limit für Performance
        
        entities = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'dates': [],
            'amounts': []
        }
        
        for ent in doc.ents:
            if ent.label_ == 'PER':
                entities['persons'].append(ent.text)
            elif ent.label_ == 'ORG':
                entities['organizations'].append(ent.text)
            elif ent.label_ in ['LOC', 'GPE']:
                entities['locations'].append(ent.text)
            elif ent.label_ == 'DATE':
                entities['dates'].append(ent.text)
            elif ent.label_ == 'MONEY':
                entities['amounts'].append(ent.text)
        
        # Deduplizieren
        for key in entities:
            entities[key] = list(set(entities[key]))
        
        return entities
    
    def enrich_paper_with_entities(self, paper: Paper) -> Paper:
        """Reichert Paper mit extrahierten Entitäten an"""
        
        text = paper.full_text or paper.abstract or paper.name
        entities = self.extract_entities_from_text(text)
        
        paper.mentioned_locations = entities['locations']
        
        return paper
    
    def geocode_locations(self, locations: List[str], city: str = "Deutschland") -> List[Dict]:
        """Geocodiert Liste von Ortsnamen"""
        
        results = []
        
        for location in locations[:10]:  # Limit für Performance
            try:
                query = f"{location}, {city}"
                result = self.geocoder.geocode(query, timeout=10)
                
                if result:
                    results.append({
                        'location': location,
                        'lat': result.latitude,
                        'lon': result.longitude,
                        'display_name': result.address
                    })
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                self.logger.warning(f"Geocoding failed for {location}: {e}")
        
        return results


# ==================== LOADER ====================

class DatabaseLoader:
    """Lädt Daten in PostgreSQL"""
    
    def __init__(self, db_config: Dict):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # SQLAlchemy Engine
        connection_string = (
            f"postgresql://{db_config['user']}:{db_config['password']}"
            f"@{db_config['host']}:{db_config.get('port', 5432)}"
            f"/{db_config['database']}"
        )
        
        self.engine = create_engine(connection_string)
        self.Session = sessionmaker(bind=self.engine)
        
        self.logger.info("Datenbankverbindung hergestellt")
    
    def create_schema(self, schema_sql_file: str):
        """Führt Schema-SQL-Datei aus"""
        
        with open(schema_sql_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        with self.engine.connect() as conn:
            # Split by statement
            for statement in schema_sql.split(';'):
                statement = statement.strip()
                if statement:
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except Exception as e:
                        self.logger.warning(f"Schema execution warning: {e}")
        
        self.logger.info("Schema erstellt/aktualisiert")
    
    def insert_meeting(self, meeting: Meeting) -> uuid.UUID:
        """Fügt Meeting in DB ein"""
        
        if not meeting.id:
            meeting.id = uuid.uuid4()
        
        with self.Session() as session:
            # Baue INSERT Statement
            insert_sql = text("""
                INSERT INTO meetings (
                    id, name, start_time, location, location_geometry,
                    meeting_type, meeting_status, source_url, source_html_path,
                    scraped_at
                ) VALUES (
                    :id, :name, :start_time, :location, 
                    ST_SetSRID(ST_MakePoint(:lon, :lat), 4326),
                    :meeting_type, :meeting_status, :source_url, :source_html_path,
                    :scraped_at
                )
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    modified_at = NOW()
                RETURNING id
            """)
            
            try:
                result = session.execute(insert_sql, {
                    'id': str(meeting.id),
                    'name': meeting.name,
                    'start_time': meeting.start_time,
                    'location': meeting.location,
                    'lat': meeting.location_lat,
                    'lon': meeting.location_lon,
                    'meeting_type': meeting.meeting_type,
                    'meeting_status': meeting.meeting_status,
                    'source_url': meeting.source_url,
                    'source_html_path': meeting.source_html_path,
                    'scraped_at': datetime.now()
                })
                session.commit()
                
                self.logger.info(f"Meeting inserted: {meeting.name}")
                return meeting.id
                
            except Exception as e:
                self.logger.error(f"Error inserting meeting: {e}")
                session.rollback()
                raise
    
    def insert_agenda_items(self, agenda_items: List[AgendaItem]):
        """Fügt Agenda Items in DB ein"""
        
        with self.Session() as session:
            for item in agenda_items:
                if not item.id:
                    item.id = uuid.uuid4()
                
                insert_sql = text("""
                    INSERT INTO agenda_items (
                        id, meeting_id, number, title, description, position,
                        result, scraped_at
                    ) VALUES (
                        :id, :meeting_id, :number, :title, :description, :position,
                        :result, :scraped_at
                    )
                    ON CONFLICT (id) DO NOTHING
                """)
                
                try:
                    session.execute(insert_sql, {
                        'id': str(item.id),
                        'meeting_id': str(item.meeting_id),
                        'number': item.number,
                        'title': item.title,
                        'description': item.description,
                        'position': item.position,
                        'result': item.result,
                        'scraped_at': datetime.now()
                    })
                except Exception as e:
                    self.logger.error(f"Error inserting agenda item: {e}")
            
            session.commit()
            self.logger.info(f"Inserted {len(agenda_items)} agenda items")
    
    def get_statistics(self) -> Dict:
        """Gibt Statistiken über die Datenbank zurück"""
        
        stats = {}
        
        with self.engine.connect() as conn:
            # Anzahl Meetings
            result = conn.execute(text("SELECT COUNT(*) FROM meetings"))
            stats['meetings'] = result.scalar()
            
            # Anzahl Agenda Items
            result = conn.execute(text("SELECT COUNT(*) FROM agenda_items"))
            stats['agenda_items'] = result.scalar()
            
            # Anzahl Papers
            result = conn.execute(text("SELECT COUNT(*) FROM papers"))
            stats['papers'] = result.scalar()
            
            # Anzahl Documents
            result = conn.execute(text("SELECT COUNT(*) FROM documents"))
            stats['documents'] = result.scalar()
            
            # Geocoded Meetings
            result = conn.execute(text(
                "SELECT COUNT(*) FROM meetings WHERE location_geometry IS NOT NULL"
            ))
            stats['geocoded_meetings'] = result.scalar()
        
        return stats


# ==================== ETL PIPELINE ====================

class StadtratETLPipeline:
    """Hauptpipeline die alles orchestriert"""
    
    def __init__(self, html_dir: str, db_config: Dict):
        self.logger = logging.getLogger(self.__class__.__name__)
        
        self.extractor = HTMLExtractor(html_dir)
        self.transformer = DataTransformer()
        self.loader = DatabaseLoader(db_config)
        
        # Scraping Run ID für diese Session
        self.scrape_run_id = uuid.uuid4()
    
    def run(self, city_name: str = "Deutschland"):
        """Führt komplette ETL-Pipeline aus"""
        
        self.logger.info("=" * 80)
        self.logger.info(f"ETL Pipeline gestartet - Run ID: {self.scrape_run_id}")
        self.logger.info("=" * 80)
        
        start_time = datetime.now()
        
        # EXTRACT
        self.logger.info("PHASE 1: EXTRACTION")
        meetings_data = self.extractor.extract_all_meetings()
        self.logger.info(f"Extrahiert: {len(meetings_data)} Meetings")
        
        # TRANSFORM & LOAD
        self.logger.info("PHASE 2: TRANSFORMATION & LOADING")
        
        for meeting, agenda_items in meetings_data:
            try:
                # Geocoding
                meeting = self.transformer.enrich_meeting_with_geocoding(meeting, city_name)
                
                # In DB laden
                meeting_id = self.loader.insert_meeting(meeting)
                
                # Agenda Items laden
                if agenda_items:
                    self.loader.insert_agenda_items(agenda_items)
                
            except Exception as e:
                self.logger.error(f"Fehler bei Meeting '{meeting.name}': {e}")
                continue
        
        # STATISTIKEN
        self.logger.info("=" * 80)
        self.logger.info("PIPELINE ABGESCHLOSSEN")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        stats = self.loader.get_statistics()
        
        self.logger.info(f"Dauer: {duration:.2f} Sekunden")
        self.logger.info(f"Statistiken:")
        for key, value in stats.items():
            self.logger.info(f"  - {key}: {value}")
        
        self.logger.info("=" * 80)


# ==================== MAIN ====================

def main():
    """Hauptfunktion"""
    
    # Konfiguration
    HTML_DUMP_DIR = "/path/to/html/dump"
    
    DB_CONFIG = {
        'host': 'localhost',
        'port': 5432,
        'database': 'stadtrat_db',
        'user': 'postgres',
        'password': 'your_password'
    }
    
    CITY_NAME = "Königsbrunn"  # Für Geocoding
    
    # Pipeline erstellen und ausführen
    pipeline = StadtratETLPipeline(HTML_DUMP_DIR, DB_CONFIG)
    pipeline.run(city_name=CITY_NAME)


if __name__ == "__main__":
    main()
