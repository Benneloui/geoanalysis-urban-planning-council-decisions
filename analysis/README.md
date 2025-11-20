# Analysis Workflow

This directory contains the scripts to run the data processing and analysis pipeline. The scripts are numbered and should be run in order.

### 1. `01_download_data.R`

-   **Purpose:** Downloads the raw data from the OParl API for a specified city.
-   **Process:** It fetches all meetings, agenda items, and the full JSON data for all papers (documents). It uses a parallel, batch-processing approach to robustly download details for thousands of papers without running out of memory.
-   **Output:** Raw `.rds` files for meetings, agenda items, and papers are saved to `data-raw/council_meetings/`.

### 2. `02_extract_pdf_text.R`

-   **Purpose:** Extracts the full text from the PDF documents linked in the raw paper data.
-   **Process:** It reads the raw papers file, finds the PDF URLs, and uses `pdftools` (with a `tesseract` OCR fallback) to download and read the text from each one. This is also done in parallel.
-   **Output:** A new file, `..._papers_with_text.rds`, which contains the paper data enriched with a `full_text` column.

### 3. `03_extract_locations.R`

-   **Purpose:** Identifies location references within the downloaded text.
-   **Process:** It combines the agenda items and the papers (with their full text) and runs a series of regular expressions to find and categorize mentions of addresses, city districts, land parcels, and development plans.
-   **Output:** A clean, non-spatial CSV file, `..._items_for_geocoding.csv`, ready for the final geocoding step.

### 4. `04_geocode_data.R`

-   **Purpose:** Converts the extracted location references into geographic coordinates.
-   **Process:** It reads the CSV from the previous step and uses a hierarchical geocoding strategy. It attempts to geocode specific addresses first and falls back to district-level geocoding for less specific items.
-   **Output:** The final, spatially-enabled dataset, saved as a `.gpkg` file in the `data/` directory.