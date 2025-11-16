# Web Scraper für Ratsinformationssysteme (RIS)

Ein robuster, konfigurierbarer Scraper für deutsche Ratsinformationssysteme.

## 🎯 Features

- ✅ **Multi-System Support**: ALLRIS, SessionNet, eSitzungsdienst, generisch
- ✅ **Auto-Detection**: Automatische Erkennung des RIS-Typs
- ✅ **Robustheit**: Retry-Logic, Rate Limiting, Error Handling
- ✅ **Fortschritt-Tracking**: Speichert Fortschritt, kann unterbrochen werden
- ✅ **Strukturierte Ausgabe**: HTML + JSON für jede Sitzung
- ✅ **Analyse-Tools**: Verstehen Sie die HTML-Struktur vor dem Scraping

## 📦 Installation

```bash
# In Ihr Projekt-Verzeichnis wechseln
cd /Users/benedikt.pilgram/Code/Geomodelierung/stadtrat-etl-pipeline

# Dependencies installieren
pip install requests beautifulsoup4 lxml tqdm pyyaml

# Oder mit requirements.txt (falls vorhanden)
pip install -r requirements_scraper.txt
```

## 🚀 Quick Start

### 1. HTML-Struktur analysieren (WICHTIG!)

Bevor Sie scrapen, analysieren Sie die Struktur:

```bash
python analyze_ris_structure.py https://ratsinfo.IhreStadt.de
```

Dies zeigt Ihnen:
- RIS-Typ (ALLRIS, SessionNet, etc.)
- HTML-Struktur
- Wichtige CSS-Selektoren
- Link-Patterns
- Datumsformate

### 2. Ersten Test-Scrape durchführen

```bash
# Nur 5 Seiten zum Testen
python ris_scraper.py https://ratsinfo.IhreStadt.de -n 5 -v

# Mit Angabe des RIS-Typs (wenn bekannt)
python ris_scraper.py https://ratsinfo.IhreStadt.de --ris-type allris -n 10
```

### 3. Vollständiges Scraping

```bash
# Alle Sitzungen scrapen (max. 100 Seiten)
python ris_scraper.py https://ratsinfo.IhreStadt.de -n 100 -o ./data/meine_stadt

# Mit Zeitfilter
python ris_scraper.py https://ratsinfo.IhreStadt.de \
    --date-from 2024-01-01 \
    --date-to 2024-12-31 \
    -n 200
```

## 📖 Detaillierte Nutzung

### Basis-Scraping

```bash
python ris_scraper.py <URL> [OPTIONEN]
```

**Argumente:**

| Argument | Beschreibung | Standard | Beispiel |
|----------|--------------|----------|----------|
| `url` | Basis-URL des RIS | *erforderlich* | `https://ratsinfo.stadt.de` |
| `-o, --output` | Output-Verzeichnis | `./scraped_data` | `-o ./meine_daten` |
| `-n, --max-pages` | Max. Anzahl Seiten | `50` | `-n 100` |
| `-r, --rate-limit` | Pause zwischen Requests (s) | `1.0` | `-r 2.0` |
| `--ris-type` | RIS-Typ (falls bekannt) | *auto-detect* | `--ris-type allris` |
| `--date-from` | Sitzungen ab Datum | - | `--date-from 2024-01-01` |
| `--date-to` | Sitzungen bis Datum | - | `--date-to 2024-12-31` |
| `-v, --verbose` | Debug-Modus | - | `-v` |

### Beispiele

**München ALLRIS scrapen:**
```bash
python ris_scraper.py https://risi.muenchen.de/risi \
    --ris-type allris \
    -n 200 \
    -o ./data/muenchen
```

**Köln SessionNet mit Zeitfilter:**
```bash
python ris_scraper.py https://ratsinformation.stadt-koeln.de \
    --ris-type sessionnet \
    --date-from 2024-01-01 \
    --date-to 2024-12-31 \
    -o ./data/koeln
```

**Unbekanntes System (Generic Scraper):**
```bash
python ris_scraper.py https://www.kleinstadt.de/ratsinformation \
    --ris-type generic \
    -n 50 \
    -r 2.0 \
    -v
```

## 🔧 Anpassung an Ihr RIS

Der Scraper muss an die spezifische HTML-Struktur angepasst werden.

### Schritt 1: Struktur analysieren

```bash
python analyze_ris_structure.py https://ratsinfo.IhreStadt.de > struktur_analyse.txt
```

Lesen Sie die Ausgabe sorgfältig und notieren Sie:
- RIS-Typ
- Link-Patterns für Sitzungen
- CSS-Selektoren für:
  - Sitzungs-Titel
  - Datum
  - Uhrzeit
  - Ort
  - Gremium
  - Tagesordnungspunkte

### Schritt 2: Scraper anpassen

Öffnen Sie `ris_scraper.py` und passen Sie die relevante Scraper-Klasse an:

#### Für ALLRIS-Systeme:

```python
class ALLRISScraper(BaseRISScraper):
    
    def scrape_meeting(self, url: str) -> Optional[ScrapedMeeting]:
        # ... (siehe Code)
        
        # ANPASSEN: Ihre Selektoren hier
        
        # Beispiel: Titel aus spezifischem Element
        title = soup.find('h1', class_='meeting-title')
        if title:
            title = title.get_text(strip=True)
        
        # Beispiel: Datum aus Tabellenzelle
        for td in soup.find_all('td', class_='datum'):
            date_text = td.get_text(strip=True)
            # ... Datum parsen
        
        # ... etc
```

### Schritt 3: Testen & Iterieren

```bash
# Test mit 1 Seite, verbose Output
python ris_scraper.py <URL> -n 1 -v

# Prüfen Sie die gespeicherten Dateien
ls -la scraped_data/html/
cat scraped_data/json/meeting_*.json | jq .

# Wenn gut, dann mehr Seiten
python ris_scraper.py <URL> -n 10
```

## 📁 Output-Struktur

```
scraped_data/
├── html/
│   ├── meeting_abc123def456.html
│   ├── meeting_789xyz123abc.html
│   └── ...
├── json/
│   ├── meeting_abc123def456.json
│   ├── meeting_789xyz123abc.json
│   └── ...
└── scraping_progress.json
```

**JSON-Format:**
```json
{
  "url": "https://...",
  "title": "Stadtratssitzung vom 15.03.2024",
  "date": "15.03.2024",
  "time": "19:00",
  "location": "Rathaus, Großer Sitzungssaal",
  "organization": "Stadtrat",
  "agenda_items": [
    {
      "number": "1.1",
      "title": "Bebauungsplan Nr. 45",
      "position": 1
    }
  ],
  "documents": [
    {
      "title": "Beschlussvorlage BP-45",
      "url": "https://.../file.pdf"
    }
  ],
  "html_content": "./scraped_data/html/meeting_abc123.html",
  "scraped_at": "2024-10-28T18:30:00"
}
```

## 🛠️ Fortgeschrittene Nutzung

### Fortschritt fortsetzen

Der Scraper speichert seinen Fortschritt automatisch. Bei Unterbrechung:

```bash
# Einfach erneut starten - bereits gescrapte URLs werden übersprungen
python ris_scraper.py <URL> -n 100
```

### Rate Limiting anpassen

Manche Systeme blockieren bei zu vielen Requests:

```bash
# Langsamer scrapen (2 Sekunden Pause)
python ris_scraper.py <URL> -r 2.0

# Sehr langsam für sensible Server
python ris_scraper.py <URL> -r 5.0
```

### Mit YAML-Config arbeiten

Erstellen Sie eine `scraper_config.yaml`:

```yaml
base_url: "https://ratsinfo.IhreStadt.de"
output_dir: "./data/meine_stadt"
max_pages: 100
rate_limit_seconds: 1.5
ris_type: "allris"
date_from: "2024-01-01"
date_to: "2024-12-31"
```

Dann laden Sie diese mit Python:

```python
import yaml
from ris_scraper import ScraperConfig, RISScraperFactory

with open('scraper_config.yaml') as f:
    config_dict = yaml.safe_load(f)

config = ScraperConfig(**config_dict)
scraper = RISScraperFactory.create(config)
meetings = scraper.scrape()
```

## 🐛 Troubleshooting

### Problem: "Connection timeout"

**Lösung:**
```bash
# Erhöhen Sie das Timeout
python ris_scraper.py <URL> -r 2.0  # Langsamer scrapen
```

### Problem: "Too many requests (429)"

**Lösung:**
```bash
# Deutlich längere Pausen
python ris_scraper.py <URL> -r 5.0
```

### Problem: "Keine Meetings gefunden"

**Mögliche Ursachen:**
1. Falsche Start-URL
2. RIS-Typ falsch erkannt
3. HTML-Struktur anders als erwartet

**Debug:**
```bash
# 1. Struktur analysieren
python analyze_ris_structure.py <URL>

# 2. Mit verbose-Modus scrapen
python ris_scraper.py <URL> -n 1 -v

# 3. RIS-Typ manuell angeben
python ris_scraper.py <URL> --ris-type allris -v
```

### Problem: "Falsche Daten extrahiert"

Die Selektoren in `ris_scraper.py` müssen angepasst werden:

1. Analysieren Sie die HTML-Struktur: `python analyze_ris_structure.py <URL>`
2. Öffnen Sie eine gespeicherte HTML-Datei im Browser
3. Inspizieren Sie die Elemente (F12 → Developer Tools)
4. Passen Sie die Selektoren in `ris_scraper.py` an
5. Testen Sie mit: `python ris_scraper.py <URL> -n 1 -v`

## 🔗 Integration mit ETL-Pipeline

Nach dem Scraping können die HTML-Dumps in die PostgreSQL-Datenbank geladen werden:

```bash
# 1. Scrapen
python ris_scraper.py <URL> -n 100 -o ./scraped_data

# 2. ETL-Pipeline ausführen
python stadtrat_etl_pipeline.py

# (stadtrat_etl_pipeline.py muss konfiguriert werden für ./scraped_data)
```

Oder direkt im ETL-Code:

```python
from stadtrat_etl_pipeline import HTMLExtractor, DatabaseLoader

# HTML-Dumps laden
extractor = HTMLExtractor("./scraped_data/html")
meetings = extractor.extract_all_meetings()

# In Datenbank laden
loader = DatabaseLoader(db_config)
for meeting, agenda_items in meetings:
    loader.insert_meeting(meeting)
    loader.insert_agenda_items(agenda_items)
```

## 📊 Beispiel-Workflow

```bash
# 1. Neue Stadt: Struktur analysieren
python analyze_ris_structure.py https://ratsinfo.neustadt.de > analyse.txt
cat analyse.txt  # Lesen und verstehen

# 2. Test-Scrape mit wenigen Seiten
python ris_scraper.py https://ratsinfo.neustadt.de -n 5 -v

# 3. Prüfen der Ergebnisse
ls -la scraped_data/html/
head scraped_data/json/meeting_*.json

# 4. Wenn gut: Vollständiges Scraping
python ris_scraper.py https://ratsinfo.neustadt.de -n 200 \
    --date-from 2024-01-01 \
    -o ./data/neustadt

# 5. In ETL-Pipeline laden
python stadtrat_etl_pipeline.py

# 6. Datenbank abfragen
psql -d stadtrat_db -c "SELECT COUNT(*) FROM meetings;"
```

## 🚨 Rechtliche Hinweise

**WICHTIG:**
- Prüfen Sie die robots.txt der Website: `https://ratsinfo.stadt.de/robots.txt`
- Respektieren Sie Rate Limits (min. 1 Sekunde zwischen Requests)
- Nutzen Sie die Daten nur für private/wissenschaftliche Zwecke
- Kommerzielle Nutzung: Fragen Sie die Stadt um Erlaubnis
- Viele RIS bieten auch OParl-APIs - nutzen Sie diese bevorzugt!

**Best Practices:**
- ✅ Rate Limiting aktivieren (min. 1s)
- ✅ Identifizierbaren User-Agent verwenden
- ✅ Nur öffentliche Daten scrapen
- ✅ Server nicht überlasten (max. 1 Request/Sekunde)
- ✅ Zwischenspeichern (kein wiederholtes Scraping derselben Daten)

## 📚 Weiterführende Ressourcen

- **OParl Standard**: https://oparl.org (bevorzugt nutzen!)
- **ALLRIS Dokumentation**: https://www.cc-egov.de
- **SessionNet**: https://sternberg.com
- **BeautifulSoup Docs**: https://www.crummy.com/software/BeautifulSoup/
- **Scrapy (Alternative)**: https://scrapy.org

## 🤝 Support & Contribution

Bei Fragen oder Problemen:
1. Prüfen Sie die Troubleshooting-Sektion
2. Analysieren Sie die HTML-Struktur mit `analyze_ris_structure.py`
3. Aktivieren Sie verbose-Modus: `-v`

Für neue RIS-Systeme: Erstellen Sie eine neue Scraper-Klasse in `ris_scraper.py`

## 📄 Lizenz

MIT License - Nutzen Sie es frei für Ihre Projekte!

---

**Happy Scraping! 🕷️**
