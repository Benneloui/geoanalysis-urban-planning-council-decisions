# Stadtratssitzungs ETL-Pipeline

PostgreSQL-basierte ETL-Pipeline für den Import von HTML-Dumps aus Ratsinformationssystemen.

## 📋 Überblick

Diese Pipeline extrahiert Daten aus HTML-Dumps von Stadtratssitzungen, reichert sie mit Named Entity Recognition (NER) und Geocoding an, und lädt sie in eine PostgreSQL/PostGIS-Datenbank.

### Features

✅ **Strukturierte Datenbankschema** nach OParl-Standard  
✅ **HTML-Parsing** mit BeautifulSoup  
✅ **Named Entity Recognition** mit spaCy  
✅ **Geocoding** mit OpenStreetMap/Nominatim  
✅ **Räumliche Daten** mit PostGIS  
✅ **Volltext-Suche** mit PostgreSQL  
✅ **Logging & Monitoring**  
✅ **Datenqualitätsprüfung**

## 🚀 Installation

### 1. Systemvoraussetzungen

```bash
# PostgreSQL 14+ mit PostGIS
sudo apt-get install postgresql-14 postgresql-14-postgis-3

# Python 3.9+
python --version
```

### 2. Python-Abhängigkeiten

```bash
# Virtual Environment erstellen
python -m venv venv
source venv/bin/activate  # Linux/Mac
# oder
venv\Scripts\activate  # Windows

# Dependencies installieren
pip install -r requirements.txt

# spaCy Modell herunterladen
python -m spacy download de_core_news_lg
```

**requirements.txt:**
```
beautifulsoup4==4.12.2
lxml==4.9.3
psycopg2-binary==2.9.9
sqlalchemy==2.0.23
geoalchemy2==0.14.2
spacy==3.7.2
geopy==2.4.1
pandas==2.1.4
python-dateutil==2.8.2
```

### 3. Datenbank Setup

```bash
# PostgreSQL starten
sudo systemctl start postgresql

# Als postgres User
sudo -u postgres psql

# Datenbank erstellen und Schema laden
\i schema_stadtrat.sql
```

Oder via Python:

```python
from stadtrat_etl_pipeline import DatabaseLoader

db_config = {
    'host': 'localhost',
    'port': 5432,
    'database': 'stadtrat_db',
    'user': 'postgres',
    'password': 'your_password'
}

loader = DatabaseLoader(db_config)
loader.create_schema('schema_stadtrat.sql')
```

## 📁 Projektstruktur

```
stadtrat-etl/
├── stadtrat_etl_pipeline.py    # Haupt-ETL-Pipeline
├── schema_stadtrat.sql         # PostgreSQL Schema
├── requirements.txt            # Python Dependencies
├── README.md                   # Diese Datei
├── config/
│   └── config.yaml            # Konfiguration
├── data/
│   ├── html_dump/             # Input: HTML-Dateien
│   └── documents/             # Extrahierte PDFs
├── logs/
│   └── etl_pipeline.log       # Log-Dateien
└── tests/
    └── test_pipeline.py       # Unit Tests
```

## 🔧 Konfiguration

### config.yaml

```yaml
database:
  host: localhost
  port: 5432
  database: stadtrat_db
  user: postgres
  password: your_password

scraping:
  html_dump_dir: ./data/html_dump
  city_name: Königsbrunn
  
geocoding:
  enabled: true
  rate_limit_seconds: 1
  default_country: Deutschland
  
ner:
  enabled: true
  model: de_core_news_lg
  max_text_length: 10000

logging:
  level: INFO
  file: ./logs/etl_pipeline.log
```

## 🏃 Ausführung

### Basis-Verwendung

```python
from stadtrat_etl_pipeline import StadtratETLPipeline

# Konfiguration
HTML_DUMP_DIR = "./data/html_dump"
DB_CONFIG = {
    'host': 'localhost',
    'port': 5432,
    'database': 'stadtrat_db',
    'user': 'postgres',
    'password': 'your_password'
}
CITY_NAME = "Königsbrunn"

# Pipeline ausführen
pipeline = StadtratETLPipeline(HTML_DUMP_DIR, DB_CONFIG)
pipeline.run(city_name=CITY_NAME)
```

### Command-Line

```bash
python stadtrat_etl_pipeline.py \
    --html-dir ./data/html_dump \
    --db-host localhost \
    --db-name stadtrat_db \
    --city "Königsbrunn"
```

## 📊 Datenbankschema

### Kern-Tabellen

| Tabelle | Beschreibung | Key Fields |
|---------|--------------|-----------|
| `meetings` | Sitzungen | name, start_time, location_geometry |
| `agenda_items` | Tagesordnungspunkte | title, meeting_id, position |
| `papers` | Vorlagen/Drucksachen | reference, name, full_text |
| `documents` | PDF-Dokumente | filename, extracted_text, extracted_addresses |
| `organizations` | Gremien/Fraktionen | name, organization_type |
| `persons` | Mandatsträger | given_name, family_name |

### Beispiel-Abfragen

```sql
-- Alle Sitzungen der letzten 3 Monate
SELECT 
    name, 
    start_time, 
    location,
    ST_AsText(location_geometry) as coordinates
FROM meetings
WHERE start_time > NOW() - INTERVAL '3 months'
ORDER BY start_time DESC;

-- Volltext-Suche über alle Dokumente
SELECT 
    d.title,
    d.document_type,
    ts_rank(d.search_vector, query) as relevance
FROM documents d, 
     to_tsquery('german', 'Bebauungsplan & Wohngebiet') query
WHERE d.search_vector @@ query
ORDER BY relevance DESC
LIMIT 10;

-- Meetings mit Raumbezug in bestimmtem Gebiet (Bounding Box)
SELECT 
    m.name,
    m.location,
    COUNT(ai.id) as agenda_items_count
FROM meetings m
LEFT JOIN agenda_items ai ON ai.meeting_id = m.id
WHERE ST_Contains(
    ST_MakeEnvelope(7.40, 46.90, 7.50, 47.00, 4326),
    m.location_geometry
)
GROUP BY m.id;

-- Top 10 meistdiskutierte Themen
SELECT 
    title,
    COUNT(*) as mention_count
FROM agenda_items
WHERE title ILIKE '%Bebauungsplan%'
GROUP BY title
ORDER BY mention_count DESC
LIMIT 10;
```

## 🔍 HTML-Parsing Anpassung

Die `HTMLExtractor`-Klasse muss an die spezifische HTML-Struktur Ihres Dumps angepasst werden:

```python
class HTMLExtractor:
    def extract_meeting_from_html(self, html_path: Path) -> Optional[Meeting]:
        with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
            soup = BeautifulSoup(f.read(), 'lxml')
        
        # ANPASSEN: Ihre HTML-Struktur hier
        # Beispiel für verschiedene Strukturen:
        
        # Variante 1: Meeting-Name in H1
        name = soup.find('h1', class_='meeting-title')
        if name:
            name = name.get_text(strip=True)
        
        # Variante 2: Datum in <div class="meeting-date">
        date_div = soup.find('div', class_='meeting-date')
        if date_div:
            date_text = date_div.get_text(strip=True)
            start_time = date_parser.parse(date_text, dayfirst=True)
        
        # Variante 3: Tagesordnung als Tabelle
        agenda_table = soup.find('table', {'id': 'agenda'})
        # ... etc
        
        return Meeting(name=name, start_time=start_time, ...)
```

### Debugging HTML-Struktur

```python
from bs4 import BeautifulSoup

with open('sample.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'lxml')

# Alle divs mit "date" im class-Namen
print(soup.find_all('div', class_=re.compile(r'date', re.I)))

# Alle Tabellen
for table in soup.find_all('table'):
    print(table.get('class'), table.get('id'))

# Struktur inspizieren
print(soup.prettify()[:1000])
```

## 🧪 Testing

```bash
# Unit Tests
pytest tests/test_pipeline.py

# Einzelne Komponenten testen
python -c "
from stadtrat_etl_pipeline import HTMLExtractor
extractor = HTMLExtractor('./data/html_dump')
meetings = extractor.extract_all_meetings()
print(f'Gefunden: {len(meetings)} Meetings')
"
```

## 📈 Monitoring & Logs

### Log-Analyse

```bash
# Fehler anzeigen
grep ERROR logs/etl_pipeline.log

# Statistiken
tail -f logs/etl_pipeline.log | grep "STATISTIKEN"
```

### Datenbank-Monitoring

```sql
-- Scraping Log
SELECT 
    scrape_run_id,
    status,
    records_inserted,
    processing_time_seconds,
    started_at
FROM scraping_log
ORDER BY started_at DESC
LIMIT 10;

-- Datenqualität
SELECT 
    table_name,
    issue_type,
    severity,
    COUNT(*) as issue_count
FROM data_quality_issues
WHERE status = 'open'
GROUP BY table_name, issue_type, severity
ORDER BY issue_count DESC;
```

## 🔒 Best Practices

### 1. Datenqualität

```python
# Validierung nach Import
def validate_data():
    with engine.connect() as conn:
        # Test: Alle Meetings haben Namen
        result = conn.execute(text(
            "SELECT COUNT(*) FROM meetings WHERE name IS NULL OR name = ''"
        ))
        if result.scalar() > 0:
            logger.error("Meetings ohne Namen gefunden!")
        
        # Test: Geocoding Erfolgsrate
        result = conn.execute(text("""
            SELECT 
                COUNT(*) FILTER (WHERE location_geometry IS NOT NULL) * 100.0 / COUNT(*) as geocoding_rate
            FROM meetings
            WHERE location IS NOT NULL
        """))
        rate = result.scalar()
        logger.info(f"Geocoding-Erfolgsrate: {rate:.1f}%")
```

### 2. Incremental Updates

```python
# Nur neue Daten seit letztem Run
def extract_new_meetings(last_run_timestamp):
    html_files = sorted(
        html_dir.rglob('*.html'),
        key=lambda p: p.stat().st_mtime
    )
    
    new_files = [
        f for f in html_files
        if datetime.fromtimestamp(f.stat().st_mtime) > last_run_timestamp
    ]
    
    return new_files
```

### 3. Error Handling

```python
# Robuste Verarbeitung
for html_file in html_files:
    try:
        meeting = extractor.extract_meeting_from_html(html_file)
        loader.insert_meeting(meeting)
    except Exception as e:
        logger.error(f"Fehler bei {html_file}: {e}")
        # Log in data_quality_issues Tabelle
        log_quality_issue(
            table_name='meetings',
            issue_type='extraction_error',
            issue_description=str(e),
            severity='warning'
        )
        continue  # Weiter mit nächster Datei
```

## 🌐 Geocoding-Optimierung

### Rate Limiting

```python
from functools import lru_cache
import time

class CachedGeocoder:
    def __init__(self):
        self.geocoder = Nominatim(user_agent="stadtrat_etl")
        self.cache = {}
    
    @lru_cache(maxsize=1000)
    def geocode(self, address, city):
        # Cache-Lookup
        cache_key = f"{address}_{city}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Rate limiting
        time.sleep(1)
        
        # Geocode
        result = self.geocoder.geocode(f"{address}, {city}")
        
        # Cache speichern
        self.cache[cache_key] = result
        return result
```

## 📝 Erweiterungen

### 1. PDF-Extraktion hinzufügen

```python
# Document-AI für PDF-Texte
import docling

def extract_pdf_text(pdf_path):
    result = docling.convert(pdf_path)
    return result.markdown
```

### 2. Embeddings für semantische Suche

```python
# pgvector Extension
CREATE EXTENSION vector;

ALTER TABLE documents 
ADD COLUMN embedding vector(384);

# Python: Sentence-Transformers
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
embedding = model.encode(document_text)

# In DB speichern
conn.execute(
    "UPDATE documents SET embedding = %s WHERE id = %s",
    (embedding.tolist(), doc_id)
)
```

### 3. REST API

```python
# FastAPI Endpoint
from fastapi import FastAPI

app = FastAPI()

@app.get("/meetings")
async def get_meetings(limit: int = 10):
    with engine.connect() as conn:
        result = conn.execute(text(
            "SELECT * FROM v_meetings_full LIMIT :limit"
        ), {"limit": limit})
        return result.fetchall()
```

## 🐛 Troubleshooting

### Problem: Geocoding schlägt fehl

```python
# Debug-Modus
geocoder = Nominatim(user_agent="stadtrat_etl", timeout=10)
result = geocoder.geocode("Rathaus, Königsbrunn", debug=True)
print(result.raw)
```

### Problem: Encoding-Fehler

```python
# Verschiedene Encodings probieren
encodings = ['utf-8', 'iso-8859-1', 'windows-1252']
for enc in encodings:
    try:
        with open(html_file, 'r', encoding=enc) as f:
            content = f.read()
        break
    except UnicodeDecodeError:
        continue
```

### Problem: SQL Performance

```sql
-- Analyze & Vacuum
ANALYZE meetings;
VACUUM ANALYZE meetings;

-- Query Performance
EXPLAIN ANALYZE
SELECT * FROM meetings WHERE start_time > NOW() - INTERVAL '1 year';
```

## 📚 Verwandte Ressourcen

- [OParl Standard](https://oparl.org) - Standard für Ratsinformationssysteme
- [PostgreSQL Full Text Search](https://www.postgresql.org/docs/current/textsearch.html)
- [PostGIS Documentation](https://postgis.net/documentation/)
- [spaCy NER Guide](https://spacy.io/usage/linguistic-features#named-entities)
- [BeautifulSoup Docs](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)

## 📄 Lizenz

MIT License - siehe LICENSE Datei

## 👥 Kontakt & Support

Bei Fragen oder Problemen öffnen Sie ein Issue im Repository.

---

**Hinweis**: Diese Pipeline ist ein Template und muss an die spezifische HTML-Struktur Ihres Ratsinformationssystems angepasst werden.
