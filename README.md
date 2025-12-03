# Geomodelierung - Analysis of Municipal Council Decisions

## Summary

This project investigates municipal council decisions in **Augsburg, Germany**. By leveraging the **OParl API** interface, unstructured parliamentary documents (session data and papers) are transformed into structured datasets. The project applies a **hybrid extraction pipeline** combining Named Entity Recognition (NER), Fuzzy Matching, and OpenStreetMap validation to geolocate political activities. The analysis aims to reveal patterns of the council and spatial distributions of political attention (e.g., center vs. periphery bias).

## Background and Motivation

Urban planning is a core function of local government, yet the patterns of these decisions often remain hidden in thousands of PDF documents. While digitization standards like **OParl** exist, they are rarely used for quantitative spatial analysis.


## Objectives & Research Questions

**Primary Research Question:**

> "How is political attention distributed spatially across the districts of Augsburg, and what temporal patterns define the council's workflow?"

**Sub-questions:**

1. **Temporal:** When does the council meet? Are there significant shifts in meeting frequencies or times over the legislative period (2020–2025)?

2. **Spatial:** How is political attention (measured by parliamentary activity) distributed spatially across the districts of Augsburg, and does a center-periphery bias exist?


## Methodology & Implementation

The project moves beyond simple keyword searching by implementing a **Python-based ETL pipeline** (Extract, Transform, Load).

#### 1. Data

- **Source:** Official OParl API of the City of Augsburg (SessionNet).


#### 2. The "Location Extractor"

To solve the problem of unstructured location data in titles (e.g., _"Sanierung der Maxstr."_), a three-stage extraction logic is developed:

1. **NER (Named Entity Recognition):** Using `spaCy` (model: `de_core_news_sm`) to identify location entities in text context.

2. **Ground Truth Validation:** Extracted tokens are matched against a local **OpenStreetMap (OSM) dataset** containing all validated street names in Augsburg (via Overpass API).

3. **Fuzzy Matching:** Using Levenshtein distance (`thefuzz`) to map typos or abbreviations in documents to the correct OSM street name before geocoding.

## Preliminary Results (Proof of Concept)

A pilot run of the data pipeline has validated the feasibility:

- **Data Base:** Successfully harvested **~750 meetings** from Jan 2020 to Nov 2025.

- **Geocoding Success:** The streetnames form the meta Date got successfully geocoded to coordinates.


## Challenges
- Augsburg uses NON-STANDARD OParl endpoint names
- need to analyse the Augsburg OParl Standart first

## Tools & Stack

- **Language:** Mainly Python (VS Code Environment)

- **Data Fetching:** `requests` (with Retry-Adapter)

- **NLP & Matching:** `spaCy`, `thefuzz`

- **Geodata:** `geopy` (Nominatim), `Overpass API` (OSM)

- **Analysis/Viz:** `pandas`, `matplotlib`, `folium`

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
- GitHub: [@benneloui](https://github.com/benneloui)


