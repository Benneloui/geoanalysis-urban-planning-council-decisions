# Geomodelierung - Analysis of Municipal Council Decisions

**Automatisierte Extraktion, Geocodierung und Analyse von kommunalen Ratsbeschlüssen aus OParl-APIs**

Dieses Projekt untersucht Ratsbeschlüsse in Augsburg unter Verwendung der OParl-API. Die Pipeline extrahiert automatisch Ortsinformationen aus PDF-Dokumenten, geocodiert diese und stellt die Ergebnisse in verschiedenen Formaten bereit (Parquet, RDF/Linked Data, GeoJSON).

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![R Version](https://img.shields.io/badge/R-%3E%3D%204.3.0-blue.svg)](https://www.r-project.org/)

## 🎯 Features

### Core Pipeline
- ✅ **OParl API Integration** - Automatisches Abrufen von Ratsbeschlüssen
- ✅ **PDF Text Extraction** - Multi-Strategie (PyMuPDF → pdfplumber → OCR)
- ✅ **Location Extraction** - NER + Regex für Straßen, B-Pläne, Flurstücke
- ✅ **Geocoding** - Hierarchisches Geocoding mit Nominatim
- ✅ **Multi-Format Output** - Parquet, RDF/Turtle, GeoJSON
- ✅ **Crash Recovery** - SQLite-basiertes State Management
- ✅ **Batch Processing** - Effiziente Verarbeitung großer Datenmengen

### Data Enrichment (Optional)
- 🔗 **Wikidata Linking** - Verknüpfung mit Wikidata-Entities
- 🌍 **GeoNames Integration** - Administrative Hierarchien
- 🏷️ **Topic Categorization** - ML-basierte Themenkategorisierung
- 💬 **Sentiment Analysis** - Sentiment-Analyse deutscher Texte

### Quality Assurance
- ✅ **Comprehensive Test Suite** - 80+ Unit & Integration Tests
- ✅ **SHACL Validation** - RDF Shape Validation
- ✅ **Data Quality Checks** - Automatische Validierung
- ✅ **Coverage Reports** - HTML Coverage Reports

## 📂 Project Structure

```
Geomodelierung/
├── src/                      # Core modules
│   ├── client.py            # OParl API client
│   ├── extraction.py        # PDF text extraction
│   ├── storage.py           # Parquet/RDF/GeoJSON writers
│   ├── state.py             # State management & checkpoints
│   ├── spatial.py           # Location extraction & geocoding
│   ├── validation.py        # SHACL & data quality validation
│   └── enrichment.py        # Wikidata/GeoNames/ML enrichment
├── scripts/
│   └── run_pipeline.py      # Main orchestration script
├── tests/                    # Test suite
│   ├── conftest.py          # Shared fixtures
│   ├── test_client.py       # Client tests
│   ├── test_extraction.py   # Extraction tests
│   ├── test_storage.py      # Storage tests
│   ├── test_state.py        # State tests
│   ├── test_spatial.py      # Spatial tests
│   ├── test_integration.py  # Integration tests
│   └── run_tests.py         # Test runner
├── data/                     # Output directory
│   ├── papers_parquet/      # Parquet datasets
│   ├── ttl/                 # RDF/Turtle files
│   └── *.geojson           # GeoJSON for mapping
├── config.yaml              # Configuration
├── requirements.txt         # Python dependencies
├── pytest.ini              # Test configuration
├── QUICKSTART.md           # Quick start guide
├── TESTING.md              # Testing documentation
├── ENRICHMENT.md           # Enrichment documentation
└── IMPLEMENTATION_SUMMARY.md

## 🚀 Quick Start

### 1. Installation

```bash
# Clone repository
git clone https://github.com/benneloui/geoanalysis-urban-planning-council-decisions.git
cd geoanalysis-urban-planning-council-decisions

# Create virtual environment
python -m venv env
source env/bin/activate  # On Windows: env\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download de_core_news_lg
```

### 2. Test-Run

```bash
# Quick test with 10 papers
python scripts/run_pipeline.py --test

# Output:
# ✓ data/papers_parquet/         (Papers + Locations)
# ✓ data/ttl/augsburg_oparl.ttl  (RDF Graph)
# ✓ data/augsburg_locations.geojson
```

### 3. Production Run

```bash
# Full pipeline for Augsburg
python scripts/run_pipeline.py --city augsburg

# With date range
python scripts/run_pipeline.py \
    --city augsburg \
    --start-date 2024-01-01 \
    --end-date 2024-12-31

# Incremental update
python scripts/run_pipeline.py \
    --city augsburg \
    --start-date 2024-12-01
```

## 📊 Usage Examples

### Python: Load and Analyze Data

```python
import pandas as pd
import geopandas as gpd

# Load papers
papers_df = pd.read_parquet('data/papers_parquet')
print(f"Papers: {len(papers_df)}")

# Load locations
locations_df = pd.read_parquet('data/papers_parquet')
locations_df = locations_df[locations_df['coordinates'].notna()]
print(f"Geocoded locations: {len(locations_df)}")

# Create map
gdf = gpd.read_file('data/augsburg_locations.geojson')
gdf.plot(figsize=(10, 10))
```

### SPARQL: Query RDF Graph

```sparql
PREFIX oparl: <https://schema.oparl.org/1.1/>
PREFIX geo: <http://www.w3.org/2003/01/geo/wgs84_pos#>

SELECT ?paper ?name ?location ?lat ?lon
WHERE {
  ?paper a oparl:Paper ;
         oparl:name ?name ;
         geo:location ?loc .
  ?loc geo:lat ?lat ;
       geo:long ?lon .
}
LIMIT 10
```

### Web Map (Leaflet/Mapbox)

```javascript
// Load GeoJSON
fetch('data/augsburg_locations.geojson')
  .then(response => response.json())
  .then(data => {
    L.geoJSON(data, {
      onEachFeature: (feature, layer) => {
        layer.bindPopup(`
          <b>${feature.properties.text}</b><br>
          Type: ${feature.properties.type}<br>
          <a href="${feature.properties.pdf_url}">PDF öffnen</a>
        `);
      }
    }).addTo(map);
  });
```

## 🧪 Testing

```bash
# Run all tests
python tests/run_tests.py

# Unit tests only
python tests/run_tests.py --unit

# With coverage report
python tests/run_tests.py --coverage

# Fast tests (skip slow ones)
python tests/run_tests.py --fast
```

See [TESTING.md](TESTING.md) for detailed documentation.

## ✅ Validation

```python
from src.validation import ValidationReportGenerator
from rdflib import Graph

# Load RDF graph
graph = Graph()
graph.parse('data/ttl/augsburg_oparl.ttl', format='turtle')

# Validate
generator = ValidationReportGenerator(Path('validation_reports'))
report = generator.generate_report(rdf_graph=graph)

# Generate HTML report
generator.save_report(report, format='html')

print(f"Valid: {report.is_valid()}")
print(f"Errors: {report.summary['errors']}")
```

## 🔗 Enrichment (Optional)

```python
from src.enrichment import WikidataEnricher, TopicCategorizer

# Wikidata linking
enricher = WikidataEnricher()
location = {'text': 'Maximilianstraße', 'type': 'street'}
enriched = enricher.link_location(location, city='Augsburg')
print(f"Wikidata: {enriched.wikidata_id}")

# Topic categorization
categorizer = TopicCategorizer()
paper = {'name': 'Bebauungsplan...', 'pdf_text': '...'}
categorized = categorizer.categorize_paper(paper)
print(paper['categories'])
```

See [ENRICHMENT.md](ENRICHMENT.md) for detailed documentation.

## 📖 Documentation

- **[QUICKSTART.md](QUICKSTART.md)** - Schnelleinstieg für User
- **[TESTING.md](TESTING.md)** - Testing & Validation Guide
- **[ENRICHMENT.md](ENRICHMENT.md)** - Data Enrichment Guide
- **[Proposal.md](Proposal.md)** - Original Project Proposal
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Implementation Details

## 🛠️ Configuration

Edit `config.yaml`:

```yaml
oparl:
  system_url: "https://ris.augsburg.de/oparl/v1.1"
  timeout: 30
  retry_count: 3

extraction:
  batch_size: 10
  use_ocr: false

geocoding:
  service: "nominatim"
  rate_limit: 1

storage:
  base_path: "data"
  parquet:
    partition_cols: ["city", "year"]
```

## 📦 Dependencies

Core dependencies:
- `requests`, `pandas`, `pyarrow`, `pyyaml`
- `rdflib` (RDF/Linked Data)
- `geopy` (Geocoding)
- `PyMuPDF`, `pdfplumber` (PDF extraction)
- `spacy` (NER)

Optional:
- `pytest`, `pytest-cov` (Testing)
- `pyshacl` (SHACL validation)
- `transformers`, `torch` (Sentiment analysis)

See [requirements.txt](requirements.txt) for full list.

## 🤝 Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Add tests for new features
4. Submit a pull request

## 📝 License

- **Code:** MIT License
- **Documentation:** CC-BY 4.0

## 👤 Contact

**Benedikt Pilgram**
- Email: benedikt.pilgram@student.unibe.ch
- GitHub: [@benneloui](https://github.com/benneloui)

## 🙏 Acknowledgments

- OParl API: https://oparl.org/
- Wikidata: https://www.wikidata.org/
- GeoNames: https://www.geonames.org/
- Stadt Augsburg Open Data

---

See also the project proposal: [Proposal.md](Proposal.md)
