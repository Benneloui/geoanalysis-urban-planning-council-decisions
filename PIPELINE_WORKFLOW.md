# OParl Pipeline Workflow - Dokumentation

## Kurze Zusammenfassung

**Was läd die Pipeline?**
- PDFs aus dem OParl API von Augsburg (Ratssitzungen & Agendapunkte)
- Zeitraum: **Juni 1, 2025 - Dezember 31, 2025** (konfigurierbar in `config.yaml`)
- Im `--test` Modus: Nur die ersten 10 PDFs (zum Testen)

**Was macht sie damit?**
1. Extrahiert Textinhalte aus PDFs
2. Findet Ortsangaben (Straßen, Gebäude, Adressen) mittels NER + Regex
3. Matched Ortsangaben gegen 1509 echte Augsburger Straßen (Gazetteer)
4. Speichert Ergebnisse in mehreren Formaten

**Wo werden die Daten gespeichert?**
- `data/processed/council_data.parquet` - Tabellendaten (partitioniert)
- `data/processed/metadata.nt` - RDF N-Triples (Metadaten)
- `data/processed/augsburg_map.geojson` - Kartenvisualisierung

---

## 1. FETCH PHASE: PDFs laden

### Datenquelle
```
OParl API: https://www.augsburg.sitzung-online.de/public/oparl/system
Stadt: Augsburg
Zeitraum: 2025-06-01 bis 2025-12-31
```

### Was wird geladen?
```
Papers (Dokumente) = Agendapunkte + zugehörige Dateien/PDFs

Beispielstruktur:
  Paper ID: "augsburg/2025/06/paper-123"
  Titel: "Sanierung der Ludwigstraße"
  Datum: 2025-06-15
  PDFs:
    - document-123.pdf (Bericht)
    - attachment-456.pdf (Anlage)
```

### Anzahl der PDFs (geschätzt)
| Szenario | PDFs | Grund |
|----------|------|-------|
| `--test` | ~10 | Schneller Test |
| 6-Monate (Prod) | 200-500 | Typische Ratssitzungen |
| Full Year | 400-1000 | Ganzjährig |

### Batch-Verarbeitung
```python
# config.yaml
batch_size: 50  # 50 PDFs pro Batch (Checkpoint)

# run_pipeline.py
Batch 1: PDFs 1-50
Batch 2: PDFs 51-100
...
Batch N: PDFs (N-1)*50 + 1
```

---

## 2. EXTRACT PHASE: PDFs verarbeiten

### 2A. Text-Extraktion
```
Input:  PDF file (z.B. 2MB Ratssitzungs-Bericht)
         ↓
Process: PyMuPDF (fitz) extrahiert Rohtext aus PDF
         ↓
Output: full_text = "Die Sitzung fand am 15.6.2025 statt..."
        page_count = 12
        extraction_method = "pdfplumber" oder "fitz"
```

**Performance:**
- 3 parallel workers
- ~1 Sekunde pro PDF
- Batch von 50 PDFs ≈ 17 Sekunden

### 2B. Locations extrahieren (NEUE METHODE mit Gazetteer)
```
Input:  full_text = "Sanierung der Ludwigstraße 123..."

Process:
  1. Kandidaten finden (NER + Regex)
     → "Ludwigstraße 123", "Königsplatz", "Arbeitsplatz", "Prozent"

  2. Fuzzy-Match gegen Gazetteer (1509 Straßen)
     → "Ludwigstraße" ✓ (Match 95%)
     → "Königsplatz" ✓ (Match 100%)
     → "Arbeitsplatz" ✗ (nicht in Gazetteer)
     → "Prozent" ✗ (nicht in Gazetteer)

  3. Koordinaten aus Gazetteer LADEN (kein Geocoding!)
     → Ludwigstraße: (48.3456°N, 10.8901°E)
     → Königsplatz: (48.3678°N, 10.8765°E)

Output: locations = [
  {
    "name": "Ludwigstraße",
    "latitude": 48.3456,
    "longitude": 10.8901,
    "source": "gazetteer"
  },
  {
    "name": "Königsplatz",
    "latitude": 48.3678,
    "longitude": 10.8765,
    "source": "gazetteer"
  }
]
```

**Performance:**
- KEIN Nominatim geocoding nötig
- Nur lokale Dictionary-Operationen
- ~100ms pro Paper
- 50 Papers ≈ 5 Sekunden

---

## 3. WRITE PHASE: Speichern

### 3A. Parquet (Tabellendaten)
```
Output: data/processed/council_data.parquet/

Partitionierung:
  city=augsburg/
    year=2025/
      month=06/
        part-0.parquet
        part-1.parquet
      month=07/
        part-0.parquet
      month=12/
        part-0.parquet
    year=2026/
      ...

Spalten:
  - id: "augsburg/2025/06/paper-123"
  - title: "Sanierung der Ludwigstraße"
  - date: 2025-06-15
  - full_text: "Die Sitzung fand am..."
  - locations: [{name: "Ludwigstraße", lat: 48.3456, lon: 10.8901}, ...]
  - city: "augsburg"
  - year: 2025
  - month: 6
```

**Format:** Apache Parquet (komprimiert mit Snappy)
**Größe:** ~100-200 MB für 6 Monate
**Verwendung:**
```bash
# Mit pandas lesen
import pandas as pd
df = pd.read_parquet('data/processed/council_data.parquet')
df.query('city == "augsburg" and month == 6')
```

### 3B. RDF/N-Triples (Metadaten & Ontologie)
```
Output: data/processed/metadata.nt

Format: N-Triples (append-only)
Beispiel:
  <http://example.org/oparl/paper/123>
    <http://purl.org/dc/terms/title>
    "Sanierung der Ludwigstraße" .

  <http://example.org/oparl/paper/123>
    <http://example.org/oparl/relatesToArea>
    <http://example.org/locations/ludwigstrasse> .

  <http://example.org/locations/ludwigstrasse>
    <http://www.opengis.net/ont/geosparql#asWKT>
    "POINT(10.8901 48.3456)"^^<http://www.opengis.net/ont/geosparql#wktLiteral> .
```

**Verwendung:**
- SPARQL-Abfragen (z.B. GraphDB)
- Semantic Web Integration
- Linked Open Data (LOD)


**Verwendung:** Statistische Auswertungen

### 3C. GeoJSON (Kartenvisualisierung)
```
Output: data/processed/locations.geojson

Format: GeoJSON FeatureCollection
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [10.8901, 48.3456]  # [lon, lat]
      },
      "properties": {
        "name": "Ludwigstraße",
        "count": 12,
        "source": "gazetteer"
      }
    },
    ...
  ]
}
```

**Verwendung:**
- Leaflet/Mapbox Visualisierung
- ArcGIS
- QGIS

---

## 4. STATE TRACKING (Crash Recovery)

### SQLite State Database
```
Output: data/processed/pipeline_state.db

Tabellen:
  - pipeline_runs: Historischer Überblick
    run_id, city, start_time, end_time, status, stats

  - processed_resources: Was wurde bereits verarbeitet?
    resource_id, resource_type, run_id, status
    "augsburg/2025/06/paper-123", "paper", 1, "completed"
    "augsburg/2025/06/paper-124", "paper", 1, "failed"

  - checkpoints: Für Crash-Recovery
    run_id, checkpoint_time, batch_size
```

**Feature:** Wenn Pipeline abbricht (z.B. Netzwerkfehler), kann sie später WEITERMACHEN:
```bash
# Erste Ausführung
python scripts/run_pipeline.py --city augsburg  # Crasht bei Paper 150

# Später fortsetzen
python scripts/run_pipeline.py --city augsburg  # Startet bei Paper 151
```

---

## 5. ENDE: Was dann?

Nach dem Pipeline-Lauf haben Sie:

### Datenexporte (zur Weiterverarbeitung)
```
1. council_data.parquet
   → Python (pandas) / R / SQL Abfragen
   → Tableau / Power BI
   → Machine Learning (scikit-learn, etc.)
   → Direkte Analyse in Jupyter Notebooks

2. metadata.nt / metadata.ttl
   → SPARQL Queries (GraphDB, Virtuoso, YASGUI)
   → Knowledge Graph Creation
   → Linked Open Data Publishing

3. augsburg_map.geojson
   → Kartenvisualisierungen (Leaflet, Folium)
   → GIS Analysen (QGIS, ArcGIS)
   → Interaktive Web-Maps mit PDF-Links
```
```
1. council_data.parquet
   → Python (pandas) / R / SQL Abfragen
   → Tableau / Power BI
   → Machine Learning (scikit-learn, etc.)

2. metadata.nt
   → SPARQL Queries (GraphDB, Virtuoso)
   → Knowledge Graph Creation
   → Linked Open Data Publishing


4. locations.geojson
   → Kartenvisualisierungen
   → GIS Analysen
```

### Typische Analysefragen
```
Fragen, die Sie jetzt beantworten können:

1. "Welche Stadtteile werden am häufigsten erwähnt?"
   → Group by location, count, order by count desc

2. "Welche Entwicklungen finden in Oberhausen statt?"
   → Filter locations = "Oberhausen", show associated papers

3. "Räumliche Analyse der Ratsarbeit"
   → Visualisiere alle Ortsangaben auf einer Karte

4. "Zeitreihenanalyse: Welche Gegenden kamen Oktober häufiger vor?"
   → Time series by month, location
```

---

## 6. TEST vs. PRODUKTION

### Test Mode (`--test`)
```bash
python scripts/run_pipeline.py --test --limit 10

Einstellungen:
- Limit: 10 PDFs
- Batch-Größe: 5
- Zeitraum: 2025-06-01 bis 2025-12-31
- Ausgabe: Gleiche Verzeichnisse (wird überschrieben!)

Laufzeit: ~1-2 Minuten
```

### Produktions Mode
```bash
python scripts/run_pipeline.py --city augsburg

Einstellungen:
- Limit: unbegrenzt (alle verfügbaren)
- Batch-Größe: 50
- Zeitraum: aus config.yaml
- Ausgabe: Parquet/RDF/CSV/GeoJSON

Laufzeit: 30-60 Minuten (abhängig von Anzahl PDFs)
```

---

## 7. CONFIGURATION

### Wichtige Einstellungen in `config.yaml`

```yaml
# Zeitraum für Datenfetch
oparl:
  start_date: "2025-06-01T00:00:00Z"  # Wann anfangen
  end_date: "2025-12-31T23:59:59Z"    # Wann stoppen

# Geocoding (jetzt mit Gazetteer!)
geocoding:
  verify_ssl: false  # macOS: SSL-Fehler vermeiden
  rate_limit: 1      # Verzögerung zwischen Requests (Sekunden)

# Speicherpfade
paths:
  processed: "data/processed"  # Wo speichern?

# Performance
processing:
  parquet:
    compression: "snappy"  # Kompression-Typ
```

---

## 8. HÄUFIGE PROBLEME & LÖSUNGEN

| Problem | Ursache | Lösung |
|---------|--------|--------|
| "SSL Certificate Error" | macOS SSL Issue | Setzen Sie `verify_ssl: false` in config.yaml |
| Pipeline abgebrochetag nach 5 Papers | Memory-Fehler (große PDFs) | Reduzieren Sie `batch_size` auf 10-20 |
| "Worked too fast, rate limited" | Nominatim zu schnell | Erhöhen Sie `rate_limit` auf 2-5 Sekunden |
| Locations sind NULL/None | PDF Text-Extraktion fehlgeschlagen | PDFs sind gescannte Bilder (kein OCR) |

---

## 9. NÄCHSTE SCHRITTE

Nach erfolgreichem Pipeline-Lauf:

1. **Ergebnisse validieren**
   ```bash
   python -c "
   import pandas as pd
   df = pd.read_parquet('data/processed/council_data.parquet')
   print(f'Loaded {len(df)} papers')
   print(f'With {df[\"locations\"].apply(len).sum()} total locations')
   "
   ```

2. **Visualisierungen erstellen**
   ```bash
   # GeoJSON mit Leaflet anzeigen
   python -c "
   import json
   with open('data/processed/locations.geojson') as f:
     data = json.load(f)
   print(f'Generated {len(data[\"features\"])} location features')
   "
   ```

3. **Zeitraum erweitern**
   - `config.yaml` aktualisieren
   - Pipeline erneut starten (nur neue Daten werden verarbeitet)

4. **Andere Städte testen**
   ```bash
   python scripts/run_pipeline.py --city munich
   python scripts/run_pipeline.py --city cologne
   ```

