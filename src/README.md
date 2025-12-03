# Scripts & Modules (`src/`)

This directory contains the core logic for the OParl Data Pipeline. The architecture follows a **Stream Processing** approach to handle large volumes of municipal data without local PDF storage.

- **Reusable modules:** Core logic (API, PDF, Storage) resides in `src/`.
- **Pipeline scripts:** Orchestration scripts reside in `scripts/` (e.g., `run_pipeline.py`).

## Design Principles

1.  **Separation of Concerns**:
    * `client.py`: Pure API interaction.
    * `extraction.py`: Pure PDF processing (in-memory).
    * `storage.py`: Pure I/O (Parquet/RDF).
    * `state.py`: Crash recovery.
2.  **Reusability**: Functions are generic and composable.
3.  **Documentation**: All functions have docstrings.
4.  **Error Handling**: Robust retry logic (Exponential Backoff) and state tracking (SQLite).
5.  **Traceability**: Every extracted entity (Location) must retain a link to its source document (PDF URL).

---

## Pipeline Stages

### 1. `01_download` (Ingest & Text Extraction)
*Implemented in: `scripts/run_pipeline.py` using `src.client` & `src.extraction`*

-   **Purpose:** Fetches metadata and extracts raw text while preserving source links for visualization.
-   **Process:**
    1.  **API Fetching:** Iterates through `Papers` via a generator.
    2.  **Link Preservation:** Extracts `accessUrl` (Direct PDF) and `web` (SessionNet View) from metadata.
    3.  **In-Memory Extraction:** Downloads PDF stream to memory to extract text.
    4.  **Partitioning:** Writes batches to disk.
-   **URI Strategy:**
    * Base: `http://{project.city}.oparl-analytics.org/`
    * Meeting: `{BASE_URI}/meeting/{original_id}`
    * Paper: `{BASE_URI}/paper/{original_id}`
-   **Output:**
    * **Format:** Partitioned Parquet Dataset
    * **Location:** `data/processed/parquet_parts/part_XXXXX.parquet`
    * **Content:** * `id`: Unique OParl ID
        * `name`: Document title
        * `full_text`: Extracted raw text
        * `pdf_url`: **Direct link to the PDF file (Crucial for Map Popups)**
        * `web_url`: Link to the RIS entry

### 2. `02_extraction` (Entity Recognition & Enrichment)
*Implemented in: `src/spatial.py`*

-   **Purpose:** Identifies spatial entities within the text and links them to the source PDF.
-   **Process:**
    1.  **Loading:** Reads the Parquet dataset.
    2.  **Context Preservation:** The extraction function receives the row (including `pdf_url`).
    3.  **Hybrid NER:** Extracts locations (Regex/spaCy).
    4.  **Association:** Every found location is stored as a tuple/object: `(LocationName, SourcePDF_URL)`.
-   **Output:**
    * **Format:** Enriched Parquet
    * **Content:** New column `locations` containing a list of objects: `[{"name": "Hauptstr. 1", "source": "https://..."}]`

### 3. `03_convert` (Geocoding & Semantic Mapping)
*Implemented in: `src/storage.py`*

-   **Purpose:** Converts entities to coordinates and creates the final Linked Data graph.
-   **Process:**
    1.  **Geocoding:** Appends `lat`/`lon` to the location objects.
    2.  **RDF Generation:** Maps the data to triples.
        * The `oparl:Location` object gets a property `rdfs:seeAlso` pointing to the `pdf_url`.
-   **Output:**
    * **Format:** Turtle (`.ttl`)
    * **Location:** `data/processed/knowledge_graph.ttl`
    * **Use Case:** A SPARQL query can now answer: *"Show me all construction sites in District X and give me the link to the official PDF."*
