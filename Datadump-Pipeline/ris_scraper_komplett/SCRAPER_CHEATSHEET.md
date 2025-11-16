# RIS Scraper - Cheat Sheet

## 🚀 Schnellstart-Kommandos

```bash
# Minimaler Test (5 Seiten, auto-detect)
python3 ris_scraper.py https://ratsinfo.stadt.de -n 5

# Mit vollständiger Konfiguration
python3 ris_scraper.py https://ratsinfo.stadt.de \
    --ris-type allris \
    -n 100 \
    -o ./data/stadt \
    -r 1.5 \
    --date-from 2024-01-01 \
    -v
```

## 🔍 Analyse & Debugging

```bash
# HTML-Struktur analysieren
python3 analyze_ris_structure.py https://ratsinfo.stadt.de

# Output in Datei speichern
python3 analyze_ris_structure.py https://ratsinfo.stadt.de > analyse.txt

# Verbose-Modus für Debugging
python3 ris_scraper.py <URL> -n 1 -v
```

## 📊 Verschiedene RIS-Typen

```bash
# ALLRIS (CC e-gov)
python3 ris_scraper.py https://risi.muenchen.de/risi --ris-type allris -n 50

# SessionNet (STERNBERG)
python3 ris_scraper.py https://ratsinformation.stadt-koeln.de --ris-type sessionnet -n 50

# Unbekanntes System (Generic)
python3 ris_scraper.py https://www.kleinstadt.de/rats --ris-type generic -n 30
```

## ⏰ Zeitfilter

```bash
# Nur 2024
python3 ris_scraper.py <URL> --date-from 2024-01-01 --date-to 2024-12-31

# Letzte 6 Monate
python3 ris_scraper.py <URL> --date-from $(date -d "6 months ago" +%Y-%m-%d)

# Ab bestimmtem Datum bis heute
python3 ris_scraper.py <URL> --date-from 2024-01-01
```

## 🐌 Rate Limiting

```bash
# Standard (1 Sekunde)
python3 ris_scraper.py <URL> -r 1.0

# Langsam (2 Sekunden)
python3 ris_scraper.py <URL> -r 2.0

# Sehr langsam (5 Sekunden) - für sensible Server
python3 ris_scraper.py <URL> -r 5.0
```

## 📁 Output-Organisation

```bash
# Nach Stadt organisieren
python3 ris_scraper.py <URL> -o ./data/muenchen
python3 ris_scraper.py <URL2> -o ./data/augsburg

# Mit Zeitstempel
OUTPUT="./scraped_$(date +%Y%m%d_%H%M%S)"
python3 ris_scraper.py <URL> -o "$OUTPUT"

# Verschiedene Zeiträume
python3 ris_scraper.py <URL> --date-from 2023-01-01 --date-to 2023-12-31 -o ./data/2023
python3 ris_scraper.py <URL> --date-from 2024-01-01 --date-to 2024-12-31 -o ./data/2024
```

## 🔄 Fortschritt fortsetzen

```bash
# Scraping wurde unterbrochen? Einfach erneut starten:
python3 ris_scraper.py <URL> -n 100 -o ./data/stadt

# Bereits gescrapte URLs werden übersprungen (siehe scraping_progress.json)
```

## 📊 Ergebnisse prüfen

```bash
# Anzahl HTML-Dateien
find scraped_data/html -name "*.html" | wc -l

# Anzahl JSON-Dateien
find scraped_data/json -name "*.json" | wc -l

# Erste Meeting anzeigen (mit jq)
cat scraped_data/json/meeting_*.json | head -1 | jq .

# Alle Titel auflisten
find scraped_data/json -name "*.json" -exec jq -r '.title' {} \;

# Nach Datum sortiert
find scraped_data/json -name "*.json" -exec jq -r '[.date, .title] | @tsv' {} \; | sort
```

## 🛠️ Häufige Probleme & Lösungen

### Problem: "Connection timeout"
```bash
# Lösung: Längere Pausen
python3 ris_scraper.py <URL> -r 3.0
```

### Problem: "Too many requests (429)"
```bash
# Lösung: Noch längere Pausen
python3 ris_scraper.py <URL> -r 5.0
```

### Problem: "Keine Meetings gefunden"
```bash
# 1. Struktur analysieren
python3 analyze_ris_structure.py <URL>

# 2. RIS-Typ manuell angeben
python3 ris_scraper.py <URL> --ris-type allris -v

# 3. Nur 1 Seite mit Verbose-Output
python3 ris_scraper.py <URL> -n 1 -v
```

### Problem: "Falsche Daten extrahiert"
```bash
# 1. HTML-Datei im Browser öffnen
open scraped_data/html/meeting_*.html

# 2. Developer Tools öffnen (F12)
# 3. Selektoren identifizieren
# 4. ris_scraper.py anpassen
# 5. Erneut testen
python3 ris_scraper.py <URL> -n 1 -v
```

## 🔗 Integration mit ETL-Pipeline

```bash
# 1. Scrapen
python3 ris_scraper.py <URL> -n 100 -o ./scraped_data

# 2. In Pipeline laden
python3 stadtrat_etl_pipeline.py

# (Stelle sicher, dass HTML_DUMP_DIR = "./scraped_data/html" in der ETL-Config)
```

## 📝 Mit YAML-Config

Erstelle `my_city.yaml`:
```yaml
base_url: "https://ratsinfo.stadt.de"
ris_type: "allris"
max_pages: 100
rate_limit_seconds: 1.5
output_dir: "./data/meine_stadt"
```

Dann in Python:
```python
import yaml
from ris_scraper import ScraperConfig, RISScraperFactory

with open('my_city.yaml') as f:
    config = ScraperConfig(**yaml.safe_load(f))

scraper = RISScraperFactory.create(config)
meetings = scraper.scrape()
```

## 🎯 Best Practices

```bash
# ✅ IMMER: Erst analysieren
python3 analyze_ris_structure.py <URL>

# ✅ IMMER: Erst mit wenigen Seiten testen
python3 ris_scraper.py <URL> -n 5 -v

# ✅ IMMER: Rate Limiting aktivieren (min. 1s)
python3 ris_scraper.py <URL> -r 1.0

# ✅ EMPFOHLEN: Verbose bei ersten Tests
python3 ris_scraper.py <URL> -n 10 -v

# ✅ EMPFOHLEN: Output-Verzeichnis pro Stadt
python3 ris_scraper.py <URL> -o ./data/stadt_name

# ❌ NICHT: Zu viele Requests auf einmal
python3 ris_scraper.py <URL> -r 0.1  # Zu schnell!

# ❌ NICHT: Ohne Test direkt 1000 Seiten scrapen
python3 ris_scraper.py <URL> -n 1000  # Erst testen!
```

## 🔐 Rechtliches beachten

```bash
# Prüfe robots.txt
curl https://ratsinfo.stadt.de/robots.txt

# User-Agent ist gesetzt (in ris_scraper.py)
# Rate Limiting ist aktiv (Standard: 1s)
# Nur öffentliche Daten werden gescrapt
```

## 📚 Hilfe & Dokumentation

```bash
# Hilfe-Text anzeigen
python3 ris_scraper.py --help

# Vollständige Dokumentation
cat SCRAPER_README.md

# Struktur-Analyzer Hilfe
python3 analyze_ris_structure.py --help
```

---

**Tipp:** Speichern Sie häufig genutzte Kommandos in einem Shell-Script oder Makefile!

Beispiel `scrape_muenchen.sh`:
```bash
#!/bin/bash
python3 ris_scraper.py https://risi.muenchen.de/risi \
    --ris-type allris \
    -n 200 \
    -o ./data/muenchen \
    -r 1.5 \
    --date-from 2024-01-01
```
