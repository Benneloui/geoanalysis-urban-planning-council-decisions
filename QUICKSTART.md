# Quick Start Guide - OParl Data Pipeline

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/benneloui/geoanalysis-urban-planning-council-decisions.git
cd geoanalysis-urban-planning-council-decisions
```

### 2. Create Environment

```bash
# Using conda
conda env create -f environment.yml
conda activate oparl-augsburg

# Or using pip
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate
pip install -r requirements.txt
```

### 3. Install Dependencies

```bash
# Core packages
pip install requests pandas pyarrow rdflib pyyaml geopy

# PDF extraction
pip install PyMuPDF pdfplumber

# NLP (optional but recommended)
pip install spacy thefuzz python-Levenshtein
python -m spacy download de_core_news_sm

# OCR (optional, for scanned PDFs)
# macOS: brew install tesseract
# Ubuntu: sudo apt-get install tesseract-ocr tesseract-ocr-deu
# Then: pip install pytesseract pillow
```

## Quick Test

Run a test with 10 papers to verify everything works:

```bash
python scripts/run_pipeline.py --test
```

Expected output:
```
======================================================================
OParl Pipeline Orchestrator - AUGSBURG
======================================================================
Logging to: logs/pipeline_augsburg_20241203_143022.log
Pipeline run ID: 1
...
✓ PIPELINE COMPLETED SUCCESSFULLY
```

## Configuration

Edit `config.yaml` for your needs:

```yaml
project:
  city: "augsburg"  # Change for different cities

oparl:
  endpoints:
    augsburg: "www.augsburg.sitzung-online.de/public/oparl/system"
  start_date: "2023-01-01T00:00:00Z"  # Adjust date range

processing:
  parquet:
    batch_size: 50  # Adjust for memory constraints
```

## Basic Usage

### Run Full Pipeline

```bash
# Process all papers from 2023 onwards
python scripts/run_pipeline.py
```

### Custom Date Range

```bash
python scripts/run_pipeline.py \
    --start-date 2024-01-01T00:00:00Z \
    --end-date 2024-12-31T23:59:59Z
```

### Incremental Update

```bash
# Process only new papers (skips already processed)
python scripts/run_pipeline.py --start-date 2024-11-01T00:00:00Z
```

## Output

After running, check these files:

```bash
# View locations data
python -c "
import pandas as pd
df = pd.read_parquet('data/processed/augsburg_locations.parquet')
print(df.head())
print(f'\nTotal locations: {len(df)}')
print(f'With coordinates: {df.latitude.notna().sum()}')
"

# View GeoJSON (for maps)
cat data/processed/augsburg_map.geojson | head -50
```

## Visualize on Map

### Option 1: Simple HTML Map

Create `view_map.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Augsburg Council Locations</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <style>
        #map { height: 600px; }
    </style>
</head>
<body>
    <h1>Augsburg Council Decisions - Locations</h1>
    <div id="map"></div>

    <script>
        // Initialize map
        const map = L.map('map').setView([48.369, 10.898], 12);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png').addTo(map);

        // Load GeoJSON
        fetch('data/processed/augsburg_map.geojson')
            .then(r => r.json())
            .then(data => {
                L.geoJSON(data, {
                    onEachFeature: function(feature, layer) {
                        const p = feature.properties;
                        const popup = `
                            <strong>${p.location_value}</strong><br>
                            <em>${p.location_type}</em><br>
                            <hr>
                            <strong>Paper:</strong> ${p.paper_name}<br>
                            <strong>Datum:</strong> ${p.paper_date}<br>
                            <a href="${p.pdf_url}" target="_blank">📄 PDF öffnen</a>
                        `;
                        layer.bindPopup(popup);
                    }
                }).addTo(map);
            });
    </script>
</body>
</html>
```

Open in browser: `open view_map.html`

### Option 2: Python/Folium

```python
import pandas as pd
import folium

# Load locations
df = pd.read_parquet('data/processed/augsburg_locations.parquet')
df = df[df.latitude.notna()]

# Create map
m = folium.Map(location=[48.369, 10.898], zoom_start=12)

# Add markers
for _, row in df.head(100).iterrows():
    folium.Marker(
        [row['latitude'], row['longitude']],
        popup=f"""
            <strong>{row['location_value']}</strong><br>
            {row['paper_name']}<br>
            <a href="{row['pdf_url']}" target="_blank">PDF</a>
        """,
        tooltip=row['location_value']
    ).add_to(m)

m.save('map.html')
print("Map saved to map.html")
```

## Analyze Data

### Jupyter Notebook

```bash
jupyter notebook notebooks/
```

Example analysis:

```python
import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_parquet('data/processed/augsburg_locations.parquet')

# Most mentioned locations
top_locations = df['location_value'].value_counts().head(20)
top_locations.plot(kind='barh', figsize=(10, 6))
plt.title('Top 20 Mentioned Locations')
plt.xlabel('Frequency')
plt.show()

# Location types distribution
df['location_type'].value_counts().plot(kind='pie', autopct='%1.1f%%')
plt.title('Location Types')
plt.show()

# Papers by year
papers = pd.read_parquet('data/processed/council_data.parquet')
papers['year'] = pd.to_datetime(papers['date']).dt.year
papers['year'].value_counts().sort_index().plot(kind='bar')
plt.title('Papers by Year')
plt.show()
```

### SPARQL Queries

Load RDF into GraphDB or query with rdflib:

```python
from rdflib import Graph

g = Graph()
g.parse('data/processed/metadata.ttl', format='turtle')

# Query locations with coordinates
query = """
    PREFIX geo: <http://www.opengis.net/ont/geosparql#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>

    SELECT ?label (STR(?lat) as ?latitude) (STR(?lon) as ?longitude)
    WHERE {
        ?location a geo:Feature ;
                  rdfs:label ?label ;
                  geo:lat ?lat ;
                  geo:long ?lon .
    }
    LIMIT 100
"""

for row in g.query(query):
    print(f"{row.label}: {row.latitude}, {row.longitude}")
```

## Export to Other Formats

```python
import pandas as pd

df = pd.read_parquet('data/processed/augsburg_locations.parquet')

# CSV for Excel
df.to_csv('locations.csv', index=False)

# Excel with formatting
with pd.ExcelWriter('locations.xlsx', engine='openpyxl') as writer:
    df.to_excel(writer, sheet_name='Locations', index=False)

# Shapefile for QGIS (requires geopandas)
import geopandas as gpd
gdf = gpd.GeoDataFrame(
    df[df.latitude.notna()],
    geometry=gpd.points_from_xy(df.longitude, df.latitude),
    crs='EPSG:4326'
)
gdf.to_file('locations.shp')
```

## Common Issues

### No locations extracted

Check if spaCy model is installed:
```bash
python -m spacy download de_core_news_sm
```

### Geocoding too slow

Reduce batch size or use cached results:
```bash
python scripts/run_pipeline.py --batch-size 10
```

### Out of memory

```bash
python scripts/run_pipeline.py --batch-size 10 --limit 50
```

### Import errors

Make sure you're in the project root:
```bash
cd /path/to/geoanalysis-urban-planning-council-decisions
PYTHONPATH=. python scripts/run_pipeline.py
```

## Next Steps

1. ✅ Run test pipeline
2. ✅ Check output files
3. ✅ View locations on map
4. 📊 Analyze data in Jupyter
5. 🗺️ Create interactive visualizations
6. 📝 Write custom analysis scripts

## Documentation

- **Pipeline Details**: `scripts/README.md`
- **Module Documentation**: `src/README.md`
- **Location Tracking**: `src/LOCATION_TRACKING.md`
- **API Structure**: `OPARL_API_STRUCTURE.md`

## Support

- Check logs: `logs/pipeline_*.log`
- View state: `data/processed/pipeline_state.db`
- GitHub Issues: [Create an issue](https://github.com/benneloui/geoanalysis-urban-planning-council-decisions/issues)

## Example Output

Example after successful run:

```
papers_fetched: ...
papers_processed: ...
papers_failed: 12
locations_extracted: 1,453
locations_geocoded: 892

Files created:
✓ data/processed/council_data.parquet/
✓ data/processed/augsburg_locations.parquet (892 rows)
✓ data/processed/augsburg_map.geojson (892 features)
✓ data/processed/metadata.ttl (15,234 triples)
```
