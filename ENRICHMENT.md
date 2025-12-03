# Enrichment Module Documentation

Das Enrichment-Modul erweitert die extrahierten Daten mit externen Quellen und ML-Analysen.

## 🎯 Features

### 1. **Wikidata Entity Linking**
- Verknüpfung von Locations mit Wikidata-Entities
- Zusätzliche Metadaten (Population, Elevation, Wikipedia-Links)
- SPARQL-basierte Abfragen

### 2. **GeoNames Hierarchie**
- Administrative Hierarchien (Land → Bundesland → Bezirk → Stadt)
- Alternative Namen und Übersetzungen
- Populationsdaten

### 3. **Topic Categorization**
- Automatische Kategorisierung von Dokumenten
- 10 vordefinierte Kategorien (Verkehr, Stadtentwicklung, etc.)
- Keyword-basiert oder ML-basiert (erweiterbar)

### 4. **Sentiment Analysis**
- Sentimentanalyse für deutsche Texte
- Basiert auf german-sentiment-bert Modell
- Positiv/Negativ/Neutral Klassifizierung

## 📦 Installation

### Basis (Wikidata + GeoNames)

```bash
pip install requests urllib3
```

### Mit Sentiment Analysis (optional)

```bash
pip install transformers torch
```

**⚠️ Warnung**: transformers und torch sind große Dependencies (~2GB)

## 🚀 Verwendung

### Wikidata Enrichment

```python
from src.enrichment import WikidataEnricher

enricher = WikidataEnricher()

# Einzelne Location
location = {
    'text': 'Maximilianstraße',
    'type': 'street',
    'coordinates': {'lat': 48.3689, 'lon': 10.8978}
}

enriched = enricher.link_location(location, city='Augsburg')

print(f"Wikidata ID: {enriched.wikidata_id}")
print(f"Label: {enriched.wikidata_label}")
print(f"Description: {enriched.wikidata_description}")
print(f"Wikipedia: {enriched.wikipedia_url}")
print(f"Population: {enriched.population}")
```

**Output**:
```
Wikidata ID: Q1645652
Label: Maximilianstraße
Description: Straße in Augsburg
Wikipedia: https://de.wikipedia.org/wiki/Maximilianstraße_(Augsburg)
Population: None
```

### Batch Processing

```python
locations = [
    {'text': 'Königsplatz', 'type': 'place'},
    {'text': 'Rathausplatz', 'type': 'place'},
    {'text': 'Fuggerstraße', 'type': 'street'}
]

enriched_locations = enricher.batch_link_locations(locations, city='Augsburg')

for loc in enriched_locations:
    if loc.wikidata_id:
        print(f"{loc.original_text} → {loc.wikidata_id}")
```

### GeoNames Integration

```python
from src.enrichment import GeoNamesEnricher

# GeoNames Account erforderlich (kostenlos): http://www.geonames.org/login
enricher = GeoNamesEnricher(username='your_username')

location = {'text': 'Augsburg', 'type': 'city'}
enriched_loc = enricher.enrich_location(location)

print(f"GeoNames ID: {enriched_loc['geonames_id']}")
print(f"Country: {enriched_loc['geonames_country']}")
print(f"State: {enriched_loc['geonames_admin1']}")
print(f"Population: {enriched_loc['geonames_population']}")

# Hierarchie
for level in enriched_loc['geonames_hierarchy']:
    print(f"  {level['adminLevel']}: {level['name']}")
```

**Output**:
```
GeoNames ID: 2954172
Country: Deutschland
State: Bayern
Population: 296582

Hierarchy:
  ADM0: Deutschland
  ADM1: Bayern
  ADM2: Schwaben
  PPLA: Augsburg
```

### Topic Categorization

```python
from src.enrichment import TopicCategorizer

categorizer = TopicCategorizer()

# Text kategorisieren
text = """
Der Stadtrat beschließt den Bebauungsplan Nr. 2024/01
für ein neues Wohngebiet mit 200 Wohnungen südlich der
Maximilianstraße. Das Projekt umfasst auch neue Grünflächen
und einen Spielplatz.
"""

categories = categorizer.categorize_text(text, threshold=0.2)

for category, confidence in categories:
    print(f"{category}: {confidence:.2%}")
```

**Output**:
```
Bauprojekte: 40%
Wohnungsbau: 35%
Grünflächen: 25%
```

### Custom Categories

```python
custom_categories = {
    'Klimaschutz': ['klima', 'co2', 'emission', 'energie', 'nachhaltig'],
    'Digitalisierung': ['digital', 'smart city', 'glasfaser', 'breitband'],
    'Mobilität': ['verkehr', 'rad', 'bus', 'bahn', 'auto', 'parkplatz']
}

categorizer = TopicCategorizer()
categorizer.category_keywords = custom_categories

categories = categorizer.categorize_text(text)
```

### Sentiment Analysis

```python
from src.enrichment import SentimentAnalyzer

analyzer = SentimentAnalyzer()

# Einzelner Text
text = "Die Bürger begrüßen die neuen Grünflächen sehr und freuen sich auf den Park"
sentiment = analyzer.analyze_text(text)

print(f"Sentiment: {sentiment['label']}")
print(f"Confidence: {sentiment['score']:.2%}")
```

**Output**:
```
Sentiment: positive
Confidence: 94%
```

### Paper Processing Pipeline

```python
from src.enrichment import (
    WikidataEnricher,
    TopicCategorizer,
    SentimentAnalyzer
)

# Initialize enrichers
wikidata = WikidataEnricher()
categorizer = TopicCategorizer()
sentiment = SentimentAnalyzer()

def enrich_paper(paper: dict) -> dict:
    """Enrich paper with all features"""

    # 1. Categorize
    paper = categorizer.categorize_paper(paper)

    # 2. Sentiment
    if sentiment.model_loaded:
        paper = sentiment.analyze_paper(paper)

    # 3. Enrich locations
    if 'locations' in paper:
        enriched_locs = []
        for loc in paper['locations']:
            enriched = wikidata.link_location(loc, city='Augsburg')
            enriched_locs.append(enriched)
        paper['enriched_locations'] = enriched_locs

    return paper

# Process papers
enriched_papers = [enrich_paper(p) for p in papers]
```

## 🔧 Konfiguration

### Rate Limiting

Wikidata und GeoNames haben Rate Limits:

```python
# Wikidata: ~10 req/sec (automatisch gehandelt)
enricher = WikidataEnricher()
# Built-in time.sleep(0.5) zwischen Requests

# GeoNames: Abhängig vom Account-Typ
# Free: 20.000 credits/Tag, ~2000 requests/Stunde
enricher = GeoNamesEnricher(username='your_username')
```

### Caching

Wikidata-Enricher cached automatisch:

```python
enricher = WikidataEnricher()

# Erste Abfrage: API Call
result1 = enricher.search_entity('Augsburg')

# Zweite Abfrage: Aus Cache
result2 = enricher.search_entity('Augsburg')  # Sofort

# Cache persistieren (optional)
import json
with open('wikidata_cache.json', 'w') as f:
    json.dump(enricher.cache, f)
```

## 📊 Integration in Pipeline

```python
# In scripts/run_pipeline.py

from src.enrichment import WikidataEnricher, TopicCategorizer

def process_papers_with_enrichment(papers: List[Dict]) -> List[Dict]:
    """Process papers with enrichment"""

    enricher = WikidataEnricher()
    categorizer = TopicCategorizer()

    for paper in papers:
        # Categorize
        paper = categorizer.categorize_paper(paper)

        # Enrich locations
        if 'locations' in paper:
            for loc in paper['locations']:
                enriched = enricher.link_location(loc)
                loc['wikidata_id'] = enriched.wikidata_id
                loc['wikipedia_url'] = enriched.wikipedia_url

    return papers
```

## 🎓 Advanced Usage

### Custom SPARQL Queries

```python
enricher = WikidataEnricher()

custom_query = """
SELECT ?label ?mayor ?area WHERE {
  wd:Q2749 rdfs:label ?label .
  FILTER(LANG(?label) = "de")

  OPTIONAL { wd:Q2749 wdt:P6 ?mayor . }
  OPTIONAL { wd:Q2749 wdt:P2046 ?area . }
}
"""

response = enricher.session.get(
    enricher.sparql_endpoint,
    params={'query': custom_query, 'format': 'json'}
)

data = response.json()
```

### ML-based Topic Classification

```python
from transformers import pipeline

classifier = pipeline(
    "zero-shot-classification",
    model="MoritzLaurer/mDeBERTa-v3-base-mnli-xnli"
)

text = "Bebauungsplan für neues Wohngebiet"
categories = ['Wohnungsbau', 'Verkehr', 'Kultur', 'Bildung']

result = classifier(text, categories, multi_label=True)

for label, score in zip(result['labels'], result['scores']):
    print(f"{label}: {score:.2%}")
```

## 🐛 Troubleshooting

### Wikidata Timeout

```python
# Erhöhe Timeout
enricher = WikidataEnricher()
enricher.session.get(..., timeout=30)  # Default: 15
```

### GeoNames "User does not exist"

```
GeoNamesException: user account not found
```

**Lösung**: Registriere dich auf http://www.geonames.org/login

### Sentiment Model nicht verfügbar

```
WARNING: transformers library not installed
```

**Lösung**:
```bash
pip install transformers torch
```

### Memory Error bei Transformers

```
CUDA out of memory
```

**Lösung**:
```python
# CPU-only Inference
analyzer = SentimentAnalyzer()
# Läuft automatisch auf CPU wenn keine GPU
```

## 📈 Performance Tipps

1. **Batch Processing**: Nutze `batch_link_locations()` statt einzelner Calls
2. **Caching**: Aktiviere Caching für wiederholte Abfragen
3. **Rate Limiting**: Respektiere API Limits (automatisch gehandelt)
4. **Selective Enrichment**: Enriche nur wichtige Locations/Papers
5. **Parallel Processing**: Nutze ThreadPoolExecutor für I/O-bound Tasks

```python
from concurrent.futures import ThreadPoolExecutor

def enrich_location_wrapper(loc):
    return enricher.link_location(loc)

with ThreadPoolExecutor(max_workers=5) as executor:
    enriched = list(executor.map(enrich_location_wrapper, locations))
```

## 📚 Weitere Ressourcen

- [Wikidata SPARQL Tutorial](https://www.wikidata.org/wiki/Wikidata:SPARQL_tutorial)
- [GeoNames Web Services](http://www.geonames.org/export/web-services.html)
- [Transformers Documentation](https://huggingface.co/docs/transformers/)
- [German Sentiment BERT](https://huggingface.co/oliverguhr/german-sentiment-bert)
