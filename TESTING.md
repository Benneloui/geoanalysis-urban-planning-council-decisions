# Testing & Validation Guide

Dieses Dokument beschreibt die Test- und Validierungs-Infrastruktur des Geomodelierung-Projekts.

## 📋 Übersicht

Das Projekt verfügt über:
- **Unit Tests** für alle Module (client, extraction, storage, state, spatial)
- **Integration Tests** für End-to-End Pipeline
- **SHACL Validation** für RDF Output
- **Data Quality Checks** für Papers und Locations
- **Enrichment Module** für Wikidata/GeoNames und ML-Features

## 🧪 Tests ausführen

### Installation

```bash
# Basis-Dependencies
pip install pytest pytest-cov pytest-xdist

# Alle Test-Dependencies
pip install -r requirements.txt
```

### Test-Runner verwenden

```bash
# Alle Tests
python tests/run_tests.py

# Nur Unit Tests
python tests/run_tests.py --unit

# Nur Integration Tests
python tests/run_tests.py --integration

# Mit Coverage Report
python tests/run_tests.py --coverage

# Schnelle Tests (slow Tests überspringen)
python tests/run_tests.py --fast

# Tests ohne Netzwerkzugriff
python tests/run_tests.py --no-network

# Spezifischen Test
python tests/run_tests.py -k test_client

# Parallel ausführen
python tests/run_tests.py --parallel

# Verbose Output
python tests/run_tests.py -v
```

### Direkt mit pytest

```bash
# Alle Tests
pytest tests/

# Specific Test-Datei
pytest tests/test_client.py

# Mit Coverage
pytest --cov=src --cov-report=html tests/

# Markers verwenden
pytest -m "not slow" tests/

# Parallel mit 4 Workers
pytest -n 4 tests/
```

## 📊 Test-Struktur

```
tests/
├── conftest.py              # Shared fixtures (mock_config, mock_paper, etc.)
├── __init__.py
├── run_tests.py             # Test-Runner Script
├── test_client.py           # Tests für client.py
├── test_extraction.py       # Tests für extraction.py
├── test_storage.py          # Tests für storage.py
├── test_state.py            # Tests für state.py
├── test_spatial.py          # Tests für spatial.py
└── test_integration.py      # End-to-End Integration Tests
```

### Fixtures (conftest.py)

Verfügbare Fixtures:
- `temp_dir` - Temporäres Verzeichnis für Test-Outputs
- `mock_config` - Mock Konfiguration
- `mock_paper` - Mock OParl Paper Objekt
- `mock_meeting` - Mock OParl Meeting Objekt
- `mock_pdf_text` - Mock extrahierter PDF Text
- `mock_location` - Mock extrahierte Location mit Geocoding
- `sample_rdf_graph` - Beispiel RDF Graph

## ✅ Validierung

### SHACL RDF Validation

```python
from src.validation import SHACLValidator, ValidationReportGenerator
from rdflib import Graph

# RDF Graph laden
graph = Graph()
graph.parse('data/ttl/augsburg_oparl.ttl', format='turtle')

# Validieren
validator = SHACLValidator()
issues = validator.validate(graph)

# Report generieren
generator = ValidationReportGenerator(Path('validation_reports'))
report = generator.generate_report(rdf_graph=graph)

# Report speichern
generator.save_report(report, format='html')
generator.save_report(report, format='txt')

print(f"Valid: {report.is_valid()}")
print(f"Errors: {report.summary['errors']}")
```

### Data Quality Checks

```python
from src.validation import DataQualityChecker

checker = DataQualityChecker()

# Papers validieren
papers = [...]  # Liste von Paper-Dicts
paper_issues = checker.validate_papers(papers)

# Locations validieren
locations = [...]  # Liste von Location-Dicts
location_issues = checker.validate_locations(locations)

# Parquet Dataset validieren
parquet_issues = checker.validate_parquet_dataset(Path('data/papers_parquet'))

for issue in paper_issues:
    print(f"[{issue.severity.value}] {issue.message}")
```

### Kompletter Validation Report

```python
from pathlib import Path
from src.validation import ValidationReportGenerator

generator = ValidationReportGenerator(Path('validation_reports'))

# Alles validieren
report = generator.generate_report(
    papers=papers_list,
    locations=locations_list,
    rdf_graph=rdf_graph,
    parquet_path=Path('data/papers_parquet')
)

# Reports speichern
generator.save_report(report, format='html')  # Interaktives HTML
generator.save_report(report, format='txt')   # Einfaches Text
generator.save_report(report, format='json')  # Maschinenlesbar

# Status prüfen
if report.is_valid():
    print("✓ Alle Validierungen bestanden!")
else:
    print(f"✗ {report.summary['errors']} Fehler gefunden")
```

## 🔗 Enrichment

### Wikidata Linking

```python
from src.enrichment import WikidataEnricher

enricher = WikidataEnricher()

# Einzelne Location
location = {'text': 'Maximilianstraße', 'type': 'street'}
enriched = enricher.link_location(location, city='Augsburg')

print(f"Wikidata ID: {enriched.wikidata_id}")
print(f"Wikipedia: {enriched.wikipedia_url}")
print(f"Population: {enriched.population}")

# Batch Processing
enriched_locations = enricher.batch_link_locations(locations, city='Augsburg')
```

### GeoNames Hierarchie

```python
from src.enrichment import GeoNamesEnricher

# GeoNames Username erforderlich (kostenlose Registrierung)
enricher = GeoNamesEnricher(username='your_username')

location = {'text': 'Augsburg', 'type': 'city'}
enriched = enricher.enrich_location(location)

print(f"GeoNames ID: {location['geonames_id']}")
print(f"Hierarchy: {location['geonames_hierarchy']}")
```

### Topic Categorization

```python
from src.enrichment import TopicCategorizer

categorizer = TopicCategorizer()

text = "Bebauungsplan für neues Wohngebiet mit 200 Wohnungen"
categories = categorizer.categorize_text(text)

for category, confidence in categories:
    print(f"{category}: {confidence:.2f}")

# Paper kategorisieren
paper = {'name': 'Bebauungsplan...', 'pdf_text': '...'}
categorized_paper = categorizer.categorize_paper(paper)
print(paper['categories'])
```

### Sentiment Analysis

```python
from src.enrichment import SentimentAnalyzer

# Requires transformers + german-sentiment-bert model
analyzer = SentimentAnalyzer()

text = "Die Bürger begrüßen die neuen Grünflächen sehr"
sentiment = analyzer.analyze_text(text)

print(f"Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")

# Paper analysieren
paper = analyzer.analyze_paper(paper_dict)
print(paper['sentiment'])
```

## 📈 Coverage Reports

Nach `pytest --cov=src --cov-report=html` öffnen:

```bash
open htmlcov/index.html
```

Zeigt:
- Line Coverage pro Modul
- Branch Coverage
- Ungetestete Zeilen
- Coverage Trends

## 🎯 Best Practices

### Tests schreiben

1. **Arrange-Act-Assert Pattern**:
```python
def test_example(mock_config):
    # Arrange
    client = OParlClient(mock_config)

    # Act
    result = client.fetch_papers(limit=1)

    # Assert
    assert len(result) > 0
```

2. **Mocking verwenden**:
```python
@patch('requests.get')
def test_with_mock(mock_get, mock_config):
    mock_get.return_value = Mock(status_code=200)
    # Test implementation
```

3. **Fixtures nutzen**:
```python
def test_with_fixtures(mock_config, temp_dir, mock_paper):
    # Fixtures sind automatisch verfügbar
    writer = ParquetWriter(mock_config)
    writer.write_papers_table([mock_paper])
```

### Test Markers

```python
@pytest.mark.slow
def test_long_running():
    # Langsamer Test
    pass

@pytest.mark.network
def test_with_api():
    # Test benötigt Netzwerk
    pass

@pytest.mark.optional
def test_optional_feature():
    # Test für optionales Feature
    pass
```

## 🐛 Troubleshooting

### Import Errors

```bash
# Stelle sicher, dass src im Path ist
export PYTHONPATH="${PYTHONPATH}:${PWD}/src"
```

### Missing Dependencies

```bash
# Prüfe Dependencies
python tests/run_tests.py --check-deps

# Installiere fehlende Pakete
pip install pytest pytest-cov
```

### SHACL Validation nicht verfügbar

```bash
# Installiere pyshacl
pip install pyshacl
```

### Sentiment Analysis nicht verfügbar

```bash
# Installiere transformers (große Dependencies!)
pip install transformers torch

# Lade Modell
python -c "from transformers import pipeline; pipeline('sentiment-analysis', model='oliverguhr/german-sentiment-bert')"
```

## 📚 Weitere Ressourcen

- [pytest Dokumentation](https://docs.pytest.org/)
- [SHACL Specification](https://www.w3.org/TR/shacl/)
- [Wikidata Query Service](https://query.wikidata.org/)
- [GeoNames Web Services](http://www.geonames.org/export/web-services.html)
