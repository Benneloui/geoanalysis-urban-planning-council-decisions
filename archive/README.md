# Scripts

Reusable modules for downloading, extracting, and converting OParl data into structured Parquet/RDF outputs.
Using the config.yaml file and the unterstanding of the OParl API Structure Analysis.


This directory contains the core logic for the OParl Data Pipeline. The architecture follows a Stream Processing approach to handle large volumes of municipal data without local PDF storage.

Reusable modules: Core logic (API, PDF, Storage) resides in src/.

Pipeline scripts: Orchestration scripts reside in scripts/ (e.g., run_pipeline.py).

Design Principles
Separation of Concerns:

client.py: Pure API interaction.

extraction.py: Pure PDF processing (in-memory).

storage.py: Pure I/O (Parquet/RDF).

state.py: Crash recovery.


## Properties

Structured: Modular scripts for each pipeline stage.
Versioned: Compatible with pyproject.toml and config.yaml.
Reusable: Importable from notebooks or CLI.
Clean Code: Follows software engineering best practices.

## Design Principles

Separation of Concerns: Each file handles one pipeline stage.
Reusability: Generic functions with composable interfaces.
Documentation: Type hints + docstrings (Google style).
Error Handling: Retries, fallbacks, and informative logs.
Consistency: Standardized URIs, naming, and parameter conventions.

## 1. `01_download.py`

**Purpose:**
- Downloads raw data (meetings, agenda items, papers) from the OParl API PDFs.
- Implemented in: scripts/run_pipeline.py using src.client & src.extraction
- Fetches metadata from the OParl API and extracts raw text from linked PDFs into a structured format without saving intermediate PDF files.


**Process:**

- Fetches paginated data for a specified city (e.g., Augsburg).
Uses parallel batch processing to avoid memory issues.
Downloads PDFs and extracts text using:

PyMuPDF (fast text extraction).
pdfplumber (tables).
Tesseract OCR (scanned documents, fallback).

**Output:**
- PDF Text: Stored in partitioned Parquet (data/processed/council_data.parquet/).
- State Tracking: SQLite DB (pipeline_state.db) logs processed items.


## 2. `02_extraction.py`

**Purpose:**
- takes the safed pdf text in parquet and starts to extract the data out of the pdf and sorts it in cathegories


**Process:**
- It combines the agenda items and the papers (with their full text) and runs a series of regular expressions to find and categorize mentions of addresses, city districts, land parcels, and development plans.

**Output:**
- - Annotated Parquet: Extracted entities appended to the dataset.
N-Triples: RDF statements for entities (e.g., <oparl:123> <oparl:mentionsDistrict> "Innenstadt").


## 3. `03_convert.py`

**Purpose:**
- Converts the extracted data like location and references into geographic coordinates.
- Converts extracted data to geographic coordinates and RDF.

**Process:**
- It reads the CSV from the previous step and uses a hierarchical geocoding strategy. It attempts to geocode specific addresses first and falls back to district-level geocoding for less specific items.

- Validate against SHACL shapes (optional but recommended)
from pyshacl import validate

**Output:**
-  Geo-Enriched Parquet: Coordinates added.
- Final RDF: data/processed/metadata.ttl.


## 4. `04_enrich.py`

Purpose: Enhances data with external sources (e.g., NER, Wikidata).
Process:

Uses spaCy for named entity recognition (NER).
Links to Wikidata/GeoNames for standardized references.
Output:

Enriched Parquet/RDF: Ready for SPARQL/GeoSPARQL queries.


````
from src import download, extraction, convert

# 1. Download data for Augsburg
download.run(city="augsburg", config="config.yaml")

# 2. Extract entities
extraction.run(input_dir="data/processed/council_data.parquet")

# 3. Convert to RDF
convert.run(input_nt="data/processed/metadata.nt", output_ttl="data/processed/metadata.ttl")
`````
