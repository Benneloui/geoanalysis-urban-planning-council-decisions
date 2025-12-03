# Location-to-PDF Tracking

## Übersicht

Die Pipeline stellt sicher, dass **jede extrahierte Location direkt zum ursprünglichen PDF verlinkt** ist. Dies ermöglicht es, bei der Visualisierung auf einer Karte direkt zum Quelldokument zu verlinken.

## Datenfluss

```
OParl API → Paper mit PDF URL
    ↓
PDF Download & Text-Extraktion (pdf_url wird mitgeführt)
    ↓
Location-Extraktion (paper_id + pdf_url werden jeder Location hinzugefügt)
    ↓
Geocoding (Koordinaten werden hinzugefügt, Links bleiben erhalten)
    ↓
Speicherung:
  - Parquet: Separate Locations-Tabelle mit PDF-Links
  - RDF: Location-Nodes mit sourceDocument-Property
  - GeoJSON: Features mit pdf_url in properties
```

## Datenstrukturen

### 1. Paper-Objekt (nach Extraktion)

```python
{
    "id": "https://augsburg.sitzung-online.de/paper/12345",
    "name": "Bebauungsplan Innenstadt",
    "reference": "BV/2023/123",
    "date": "2023-05-15",
    "type": "Vorlage",
    "pdf_url": "https://augsburg.sitzung-online.de/files/12345.pdf",  # ← PDF Link
    "full_text": "...",
    "locations": [...]  # siehe unten
}
```

### 2. Location-Objekt (nach Geocoding)

```python
{
    "type": "address",
    "value": "Maximilianstraße 1",
    "paper_id": "https://augsburg.sitzung-online.de/paper/12345",  # ← Paper Link
    "pdf_url": "https://augsburg.sitzung-online.de/files/12345.pdf",  # ← PDF Link
    "latitude": 48.369,
    "longitude": 10.898,
    "display_name": "Maximilianstraße 1, 86150 Augsburg",
    "method": "ner",
    "query": "Maximilianstraße 1, Augsburg, Deutschland"
}
```

### 3. Locations Parquet Tabelle

```
| location_id            | paper_id | pdf_url           | location_type | location_value        | latitude | longitude |
|------------------------|----------|-------------------|---------------|-----------------------|----------|-----------|
| 12345_address_Max_1    | 12345    | https://...pdf    | address       | Maximilianstraße 1    | 48.369   | 10.898    |
| 12345_bplan_45         | 12345    | https://...pdf    | bplan         | 45                    | null     | null      |
| 12345_district_Oberhsn | 12345    | https://...pdf    | district      | Oberhausen            | 48.380   | 10.880    |
```

**Wichtige Spalten:**
- `paper_id`: Rückverlinkung zum Paper
- `pdf_url`: **Direkter Link zum PDF** (für Map-Popups)
- `paper_name`: Name des Papiers (für Anzeige)
- `paper_date`: Datum (für Filterung)

### 4. GeoJSON für Web-Maps

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [10.898, 48.369]
      },
      "properties": {
        "location_id": "12345_address_Max_1",
        "location_type": "address",
        "location_value": "Maximilianstraße 1",
        "paper_id": "12345",
        "paper_name": "Bebauungsplan Innenstadt",
        "paper_date": "2023-05-15",
        "pdf_url": "https://augsburg.sitzung-online.de/files/12345.pdf",
        "display_name": "Maximilianstraße 1, 86150 Augsburg"
      }
    }
  ]
}
```

### 5. RDF Triples

```turtle
@prefix oparl: <http://oparl.org/schema/1.1/> .
@prefix geo: <http://www.opengis.net/ont/geosparql#> .

<http://augsburg.oparl-analytics.org/paper/12345>
    a oparl:Paper ;
    oparl:name "Bebauungsplan Innenstadt" ;
    oparl:mainFile <https://augsburg.sitzung-online.de/files/12345.pdf> ;
    oparl:relatesToLocation <http://augsburg.oparl-analytics.org/location/12345_address_Max_1> .

<http://augsburg.oparl-analytics.org/location/12345_address_Max_1>
    a geo:Feature ;
    rdfs:label "Maximilianstraße 1"@de ;
    oparl:locationType "address" ;
    geo:hasGeometry "<...> POINT(10.898 48.369)"^^geo:wktLiteral ;
    geo:lat 48.369 ;
    geo:long 10.898 ;
    oparl:sourceDocument <https://augsburg.sitzung-online.de/files/12345.pdf> .  # ← PDF Link
```

## Verwendung

### Pipeline-Integration

```python
from src.client import OParlClient
from src.extraction import PDFExtractor
from src.spatial import SpatialProcessor
from src.storage import ParquetWriter, export_locations_for_map

# 1. Daten laden
client = OParlClient(city="augsburg")
extractor = PDFExtractor()
spatial = SpatialProcessor()

# 2. Papers mit PDF-URLs holen
papers = []
for paper in client.fetch_papers(limit_pages=10):
    text, pdf_url = extractor.extract_from_paper(paper)
    papers.append({
        'id': paper['id'],
        'name': paper['name'],
        'date': paper['date'],
        'pdf_url': pdf_url,  # ← PDF URL wird gespeichert
        'full_text': text
    })

# 3. Locations extrahieren (mit paper_id + pdf_url)
enriched_papers = spatial.enrich_papers_with_locations(papers)

# 4. Locations-Tabelle schreiben
writer = ParquetWriter()
writer.write_locations_table(
    enriched_papers,
    city="augsburg",
    output_file="data/processed/augsburg_locations.parquet"
)

# 5. GeoJSON für Map exportieren
geojson = export_locations_for_map(
    "data/processed/augsburg_locations.parquet",
    "data/output/augsburg_map.geojson",
    filter_city="augsburg"
)
```

### Map-Visualisierung (Leaflet Beispiel)

```javascript
// GeoJSON laden
fetch('augsburg_map.geojson')
  .then(response => response.json())
  .then(data => {
    L.geoJSON(data, {
      onEachFeature: function(feature, layer) {
        const props = feature.properties;

        // Popup mit PDF-Link
        const popup = `
          <strong>${props.location_value}</strong><br>
          <em>${props.location_type}</em><br>
          <hr>
          <strong>Paper:</strong> ${props.paper_name}<br>
          <strong>Datum:</strong> ${props.paper_date}<br>
          <a href="${props.pdf_url}" target="_blank">📄 PDF öffnen</a>
        `;

        layer.bindPopup(popup);
      }
    }).addTo(map);
  });
```

### SPARQL-Abfrage (Locations mit PDF-Links)

```sparql
PREFIX oparl: <http://oparl.org/schema/1.1/>
PREFIX geo: <http://www.opengis.net/ont/geosparql#>

SELECT ?location ?label ?coordinates ?pdfUrl ?paperName
WHERE {
  ?paper a oparl:Paper ;
         oparl:name ?paperName ;
         oparl:relatesToLocation ?location .

  ?location rdfs:label ?label ;
            geo:hasGeometry ?wkt ;
            oparl:sourceDocument ?pdfUrl .

  BIND(REPLACE(STR(?wkt), ".*POINT\\(([^)]+)\\).*", "$1") AS ?coordinates)
}
LIMIT 100
```

### Pandas-Analyse

```python
import pandas as pd

# Locations laden
df = pd.read_parquet("data/processed/augsburg_locations.parquet")

# Locations mit Koordinaten filtern
geocoded = df[df['latitude'].notna()]

# Nach Location-Type gruppieren
print(geocoded['location_type'].value_counts())

# Papers mit den meisten Locations
top_papers = geocoded.groupby(['paper_id', 'paper_name', 'pdf_url']).size()
print(top_papers.sort_values(ascending=False).head(10))

# Alle Locations für ein spezifisches Paper
paper_locations = df[df['paper_id'] == '12345']
for _, loc in paper_locations.iterrows():
    print(f"{loc['location_value']} → {loc['pdf_url']}")
```

## Vorteile dieser Architektur

1. **Direkte Verlinkung**: Jede Location kann direkt zum Quelldokument verlinkt werden
2. **Separate Locations-Tabelle**: Effiziente Abfragen und Filterung
3. **GeoJSON-Export**: Sofort verwendbar in Web-Maps
4. **RDF-Integration**: SPARQL-Abfragen über Locations und PDFs
5. **Flexible Analyse**: Pandas/SQL-Queries auf strukturierten Daten

## Ausgabeformate

| Format | Datei | Verwendung |
|--------|-------|------------|
| Parquet (Papers) | `council_data.parquet/` | Vollständige Paper-Daten mit Locations |
| Parquet (Locations) | `augsburg_locations.parquet` | Dedizierte Location-Tabelle für Analyse |
| GeoJSON | `augsburg_map.geojson` | Web-Mapping (Leaflet, Mapbox, etc.) |
| RDF/Turtle | `metadata.ttl` | SPARQL-Abfragen, Linked Data |
| CSV | Export via `df.to_csv()` | Excel, Tableau, QGIS |

## Nächste Schritte

1. Pipeline ausführen: `python scripts/run_pipeline.py --city augsburg`
2. Locations-Tabelle generieren
3. GeoJSON exportieren
4. Web-Map erstellen (siehe `visualization/` folder)
