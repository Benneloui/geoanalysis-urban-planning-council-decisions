# Scripts

- Reusable modules/functions
- Pipeline code
- Productive model training

Properties:
- Structured, versioned, reusable
- Imported from notebooks
- Compliant with clean software engineering


## Design Principles

1. **Separation of Concerns**: Each file has a single, clear purpose
2. **Reusability**: Functions are generic and composable
3. **Documentation**: All functions have roxygen comments
4. **Error Handling**: Graceful fallbacks and informative warnings
5. **Consistency**: Standardized naming and parameter conventions



### 1. `01_download`

-   **Purpose:** Downloads the raw data (meta and pdf) as ... from the OParl API for a specified city.
-   **Process:** It fetches all meetings, agenda items, and the full JSON data for all papers (documents). It uses a parallel, batch-processing approach to robustly download details for thousands of papers without running out of memory. It reads the raw papers file, finds the PDF URLs, and uses `pdftools` (with a `tesseract` OCR fallback) to download and read the text from each one. This is also done in parallel.

PyMuPDF (fitz) - Fast, good for text
pdfplumber - Better for tables
Tesseract OCR - For scanned documents

URI Strategy: Design a consistent URI scheme early:
pythonBASE_URI = "http://your-domain.org/oparl/"
# Examples:
# {BASE_URI}meeting/123
# {BASE_URI}agenda-item/123_1
# {BASE_URI}document/abc-def

-   **Output:**

### 2. `02_extraction`

-   **Purpose:** takes the safed pdf text in parquet and starts to extract the data out of the pdf and sorts it in cathegories
-   **Process:** It combines the agenda items and the papers (with their full text) and runs a series of regular expressions to find and categorize mentions of addresses, city districts, land parcels, and development plans.
-   **Output:**

### 3. `03_convert`

-   **Purpose:** Converts the extracted data like location and references into geographic coordinates.
-   **Process:** It reads the CSV from the previous step and uses a hierarchical geocoding strategy. It attempts to geocode specific addresses first and falls back to district-level geocoding for less specific items.

Validate against SHACL shapes (optional but recommended)
from pyshacl import validate

-   **Output:**