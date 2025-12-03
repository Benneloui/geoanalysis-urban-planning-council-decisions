"""
PDF Text Extraction
===================

Memory-efficient PDF text extraction using ephemeral storage (temporary files).
Supports large PDFs (200+ pages) without overwhelming RAM.

Strategy:
- Downloads PDF as stream to temporary file
- Extracts text from temp file
- Immediately deletes temp file
- Minimal RAM usage, disk-buffered processing

Usage:
    from src.extraction import PDFExtractor

    extractor = PDFExtractor()

    # Extract from URL (ephemeral storage)
    text = extractor.extract_from_url("https://example.com/document.pdf")

    # Extract from file bytes (also uses temp file for large PDFs)
    with open("doc.pdf", "rb") as f:
        text = extractor.extract_from_bytes(f.read())

    # Batch extraction
    results = extractor.extract_batch([paper1, paper2, paper3])
"""

import io
import logging
import time
import tempfile
import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager

# PDF libraries
try:
    import fitz  # PyMuPDF
    HAS_PYMUPDF = True
except ImportError:
    HAS_PYMUPDF = False
    logging.warning("PyMuPDF not installed - PDF extraction disabled")

try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from PIL import Image
    import pytesseract
    HAS_TESSERACT = True
except ImportError:
    HAS_TESSERACT = False

logger = logging.getLogger(__name__)


@dataclass
class PDFExtractionResult:
    """
    Result of PDF text extraction with metadata.

    Attributes:
        url: PDF URL that was processed
        success: Whether extraction succeeded
        text: Extracted text content
        method: Extraction method used (pymupdf, pdfplumber, ocr)
        page_count: Number of pages in the PDF
        file_size_kb: File size in kilobytes
        error: Error message if extraction failed
        used_ephemeral_storage: Whether temp file was used (for large PDFs)
    """
    url: str
    success: bool
    text: str = ""
    method: Optional[str] = None
    page_count: int = 0
    file_size_kb: float = 0.0
    error: Optional[str] = None
    used_ephemeral_storage: bool = False


class PDFExtractor:
    """
    Extract text from PDF files using ephemeral storage (temporary files).

    Memory-efficient approach for large PDFs (200+ pages):
    - Downloads PDF to temporary file
    - Extracts text from temp file
    - Deletes temp file immediately
    - RAM usage minimal (disk-buffered)

    Extraction strategy hierarchy:
    1. PyMuPDF (fast, good for text-based PDFs)
    2. pdfplumber (better for tables, slower)
    3. Tesseract OCR (for scanned documents, slowest)

    Attributes:
        session: Requests session for downloading PDFs
        timeout: Download timeout in seconds
        use_ocr: Enable OCR fallback for scanned PDFs
        min_text_length: Minimum text length to consider extraction successful
        max_memory_mb: Max MB to keep in memory before using temp file
    """

    def __init__(
        self,
        timeout: int = 60,
        use_ocr: bool = True,
        min_text_length: int = 100,
        ocr_language: str = "deu",
        max_memory_mb: int = 10  # Use temp file for PDFs > 10MB
    ):
        """
        Initialize PDF extractor with ephemeral storage.

        Args:
            timeout: HTTP download timeout in seconds OR config dict
            use_ocr: Enable Tesseract OCR fallback
            min_text_length: Minimum chars to consider extraction successful
            ocr_language: Tesseract language code (deu=German, eng=English)
            max_memory_mb: Max MB to keep in RAM, larger PDFs use temp files
        """
        # Handle config dict as first argument (for tests)
        if isinstance(timeout, dict):
            config = timeout
            extraction_config = config.get('extraction', {})
            self.timeout = extraction_config.get('timeout', 60)
            self.use_ocr = extraction_config.get('use_ocr', True) and HAS_TESSERACT
            self.min_text_length = 100
            self.ocr_language = "deu"
            self.max_memory_bytes = 10 * 1024 * 1024
        else:
            self.timeout = timeout
            self.use_ocr = use_ocr and HAS_TESSERACT
            self.min_text_length = min_text_length
            self.ocr_language = ocr_language
            self.max_memory_bytes = max_memory_mb * 1024 * 1024

        # Create session for downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; OParl-Pipeline/0.1)'
        })

        # Verify capabilities
        if not HAS_PYMUPDF:
            logger.warning("PyMuPDF not available - limited PDF support")

        if self.use_ocr:
            try:
                pytesseract.get_tesseract_version()
                logger.info(f"OCR enabled with language: {self.ocr_language}")
            except Exception as e:
                logger.warning(f"OCR requested but Tesseract not available: {e}")
                self.use_ocr = False

    @contextmanager
    def _temp_pdf_file(self, pdf_bytes: bytes):
        """
        Context manager for ephemeral PDF storage.

        Creates temporary file, yields path, deletes on exit.

        Args:
            pdf_bytes: PDF content as bytes

        Yields:
            Path to temporary PDF file
        """
        temp_fd = None
        temp_path = None

        try:
            # Create temporary file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='oparl_')

            # Write PDF bytes
            with os.fdopen(temp_fd, 'wb') as f:
                f.write(pdf_bytes)

            temp_fd = None  # Prevent double-close

            logger.debug(f"Created ephemeral PDF: {temp_path} ({len(pdf_bytes)} bytes)")

            yield temp_path

        finally:
            # Clean up
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except:
                    pass

            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Deleted ephemeral PDF: {temp_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_path}: {e}")

    def extract_from_url(
        self,
        url: str,
        retry_attempts: int = 3
    ) -> PDFExtractionResult:
        """
        Download PDF from URL and extract text using ephemeral storage.

        For large PDFs: streams to temp file, extracts, deletes immediately.
        For small PDFs: uses in-memory processing.

        Args:
            url: PDF download URL
            retry_attempts: Number of download retry attempts

        Returns:
            PDFExtractionResult with text and metadata
        """
        # Download PDF
        for attempt in range(retry_attempts):
            try:
                logger.debug(f"Downloading PDF from {url} (attempt {attempt + 1})")
                response = self.session.get(
                    url,
                    timeout=self.timeout,
                    stream=True
                )
                response.raise_for_status()

                # Check content length
                file_size_kb = 0.0
                content_length = response.headers.get('content-length')
                if content_length:
                    size_bytes = int(content_length)
                    file_size_kb = size_bytes / 1024
                    size_mb = size_bytes / (1024 * 1024)
                    logger.debug(f"PDF size: {size_mb:.2f} MB")

                    # For large files: stream directly to temp file
                    if size_bytes > self.max_memory_bytes:
                        logger.info(f"Large PDF ({size_mb:.1f} MB) - using ephemeral storage")
                        text, method, page_count = self._extract_from_stream_via_tempfile(response)
                        if text:
                            return PDFExtractionResult(
                                url=url,
                                success=True,
                                text=text,
                                method=method,
                                page_count=page_count,
                                file_size_kb=file_size_kb,
                                used_ephemeral_storage=True
                            )

                # Small file: in-memory processing
                pdf_bytes = io.BytesIO()
                for chunk in response.iter_content(chunk_size=8192):
                    pdf_bytes.write(chunk)

                pdf_bytes.seek(0)
                pdf_data = pdf_bytes.read()

                # Update file size if not available from headers
                if not file_size_kb:
                    file_size_kb = len(pdf_data) / 1024

                # Check actual size
                used_ephemeral = False
                if len(pdf_data) > self.max_memory_bytes:
                    logger.info(f"PDF size {len(pdf_data)/(1024*1024):.1f} MB - switching to ephemeral storage")
                    used_ephemeral = True
                    # Use temp file for extraction
                    with self._temp_pdf_file(pdf_data) as temp_path:
                        text, method, page_count = self._extract_from_file(temp_path)
                else:
                    # Small enough for memory
                    text, method, page_count = self._extract_from_bytes_internal(pdf_data)

                if text:
                    return PDFExtractionResult(
                        url=url,
                        success=True,
                        text=text,
                        method=method,
                        page_count=page_count,
                        file_size_kb=file_size_kb,
                        used_ephemeral_storage=used_ephemeral
                    )
                else:
                    return PDFExtractionResult(
                        url=url,
                        success=False,
                        error="No text extracted from PDF"
                    )

            except requests.exceptions.RequestException as e:
                logger.warning(f"Download attempt {attempt + 1} failed for {url}: {e}")
                if attempt < retry_attempts - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All download attempts failed for {url}")
                    return PDFExtractionResult(
                        url=url,
                        success=False,
                        error=f"Download failed: {str(e)}"
                    )

        return PDFExtractionResult(
            url=url,
            success=False,
            error="All download attempts failed"
        )

    def _extract_from_stream_via_tempfile(self, response: requests.Response) -> Tuple[Optional[str], Optional[str], int]:
        """
        Extract text from streaming response via temporary file.

        Streams PDF directly to temp file without loading into RAM.

        Args:
            response: Streaming HTTP response

        Returns:
            Tuple of (text, method, page_count)
        """
        temp_fd = None
        temp_path = None

        try:
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(suffix='.pdf', prefix='oparl_stream_')

            # Stream to temp file
            with os.fdopen(temp_fd, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)

            temp_fd = None
            logger.debug(f"Streamed PDF to ephemeral file: {temp_path}")

            # Extract text
            text, method, page_count = self._extract_from_file(temp_path)

            return text, method, page_count

        finally:
            # Clean up
            if temp_fd is not None:
                try:
                    os.close(temp_fd)
                except:
                    pass

            if temp_path and os.path.exists(temp_path):
                try:
                    os.unlink(temp_path)
                    logger.debug(f"Deleted ephemeral stream file: {temp_path}")
                except Exception as e:
                    logger.warning(f"Could not delete temp file {temp_path}: {e}")

    def _extract_from_file(self, file_path: str) -> Tuple[Optional[str], Optional[str], int]:
        """
        Extract text from PDF file on disk.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (text, method, page_count)
        """
        # Try PyMuPDF first (fastest)
        if HAS_PYMUPDF:
            text, page_count = self._extract_pymupdf_from_file(file_path)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"PyMuPDF extraction: {len(text)} chars, {page_count} pages")
                return text, 'pymupdf', page_count

        # Try pdfplumber (better for tables)
        if HAS_PDFPLUMBER:
            text, page_count = self._extract_pdfplumber_from_file(file_path)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"pdfplumber extraction: {len(text)} chars, {page_count} pages")
                return text, 'pdfplumber', page_count

        # Try OCR as last resort
        if self.use_ocr and HAS_PYMUPDF:
            text, page_count = self._extract_ocr_from_file(file_path)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"OCR extraction: {len(text)} chars, {page_count} pages")
                return text, 'ocr', page_count

        logger.warning("All extraction methods failed or returned insufficient text")
        return None, None, 0

    def extract_from_bytes(self, pdf_bytes: bytes) -> PDFExtractionResult:
        """
        Extract text from PDF bytes using ephemeral storage for large files.

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            PDFExtractionResult with text and metadata
        """
        file_size_kb = len(pdf_bytes) / 1024
        used_ephemeral = False

        # For large PDFs: use temp file
        if len(pdf_bytes) > self.max_memory_bytes:
            logger.debug(f"Large PDF ({len(pdf_bytes)/(1024*1024):.1f} MB) - using ephemeral storage")
            used_ephemeral = True
            with self._temp_pdf_file(pdf_bytes) as temp_path:
                text, method, page_count = self._extract_from_file(temp_path)
        else:
            # Small PDFs: in-memory extraction
            text, method, page_count = self._extract_from_bytes_internal(pdf_bytes)

        if text:
            return PDFExtractionResult(
                url="<bytes>",
                success=True,
                text=text,
                method=method,
                page_count=page_count,
                file_size_kb=file_size_kb,
                used_ephemeral_storage=used_ephemeral
            )
        else:
            return PDFExtractionResult(
                url="<bytes>",
                success=False,
                error="No text extracted from PDF bytes"
            )

    def _extract_from_bytes_internal(self, pdf_bytes: bytes) -> Tuple[Optional[str], Optional[str], int]:
        """
        Internal method to extract text from PDF bytes (in-memory only).

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Tuple of (text, method, page_count)
        """
        # Try PyMuPDF first (fastest)
        if HAS_PYMUPDF:
            text, page_count = self._extract_pymupdf_from_bytes(pdf_bytes)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"PyMuPDF extraction: {len(text)} chars")
                return text, 'pymupdf', page_count

        # Try pdfplumber (better for tables)
        if HAS_PDFPLUMBER:
            text, page_count = self._extract_pdfplumber_from_bytes(pdf_bytes)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"pdfplumber extraction: {len(text)} chars")
                return text, 'pdfplumber', page_count

        # Try OCR as last resort
        if self.use_ocr and HAS_PYMUPDF:
            text, page_count = self._extract_ocr_from_bytes(pdf_bytes)
            if text and len(text) >= self.min_text_length:
                logger.debug(f"OCR extraction: {len(text)} chars")
                return text, 'ocr', page_count

        logger.warning("All extraction methods failed or returned insufficient text")
        return None, None, 0

    # === File-based extraction methods (for ephemeral storage) ===

    def _extract_pymupdf_from_file(self, file_path: str) -> Tuple[Optional[str], int]:
        """
        Extract text using PyMuPDF from file.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            doc = fitz.open(file_path)
            text_parts = []
            page_count = len(doc)

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()

                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n".join(text_parts)
            return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"PyMuPDF file extraction failed: {e}")
            return None, 0

    def _extract_pdfplumber_from_file(self, file_path: str) -> Tuple[Optional[str], int]:
        """
        Extract text using pdfplumber from file.

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            with pdfplumber.open(file_path) as pdf:
                text_parts = []
                page_count = len(pdf.pages)

                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

                    # Also extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        table_text = "\n".join(["\t".join(str(cell) for cell in row if cell) for row in table if row])
                        text_parts.append(table_text)

                full_text = "\n".join(text_parts)
                return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"pdfplumber file extraction failed: {e}")
            return None, 0

    def _extract_ocr_from_file(self, file_path: str) -> Tuple[Optional[str], int]:
        """
        Extract text using Tesseract OCR from file (for scanned PDFs).

        Args:
            file_path: Path to PDF file

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            doc = fitz.open(file_path)
            text_parts = []
            page_count = len(doc)

            # Process first 10 pages max (OCR is slow)
            max_pages = min(10, page_count)

            for page_num in range(max_pages):
                page = doc[page_num]

                # Convert page to image
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))

                # Run OCR
                text = pytesseract.image_to_string(
                    img,
                    lang=self.ocr_language
                )

                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n".join(text_parts)
            return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"OCR file extraction failed: {e}")
            return None, 0

    # === In-memory extraction methods (for small PDFs) ===

    def _extract_pymupdf_from_bytes(self, pdf_bytes: bytes) -> Tuple[Optional[str], int]:
        """
        Extract text using PyMuPDF (fitz).

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            page_count = len(doc)

            for page_num in range(page_count):
                page = doc[page_num]
                text = page.get_text()

                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n".join(text_parts)
            return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"PyMuPDF extraction failed: {e}")
            return None, 0

    def _extract_pdfplumber_from_bytes(self, pdf_bytes: bytes) -> Tuple[Optional[str], int]:
        """
        Extract text using pdfplumber from bytes (in-memory, better for tables).

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                text_parts = []
                page_count = len(pdf.pages)

                for page in pdf.pages:
                    text = page.extract_text()
                    if text:
                        text_parts.append(text)

                    # Also extract tables
                    tables = page.extract_tables()
                    for table in tables:
                        table_text = "\n".join(["\t".join(row) for row in table if row])
                        text_parts.append(table_text)

                full_text = "\n".join(text_parts)
                return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"pdfplumber extraction failed: {e}")
            return None, 0

    def _extract_ocr_from_bytes(self, pdf_bytes: bytes) -> Tuple[Optional[str], int]:
        """
        Extract text using Tesseract OCR from bytes (in-memory, for scanned PDFs).

        Args:
            pdf_bytes: PDF file as bytes

        Returns:
            Tuple of (extracted text or None, page_count)
        """
        try:
            doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            text_parts = []
            page_count = len(doc)

            # Process first 10 pages max (OCR is slow)
            max_pages = min(10, page_count)

            for page_num in range(max_pages):
                page = doc[page_num]

                # Convert page to image
                pix = page.get_pixmap(dpi=150)
                img_bytes = pix.tobytes("png")
                img = Image.open(io.BytesIO(img_bytes))

                # Run OCR
                text = pytesseract.image_to_string(
                    img,
                    lang=self.ocr_language
                )

                if text:
                    text_parts.append(text)

            doc.close()

            full_text = "\n".join(text_parts)
            return (full_text if full_text.strip() else None, page_count)

        except Exception as e:
            logger.debug(f"OCR extraction failed: {e}")
            return None, 0

    def extract_from_paper(self, paper: Dict[str, Any]) -> Tuple[PDFExtractionResult, Optional[str]]:
        """
        Extract text from an OParl paper object.

        Args:
            paper: OParl paper dictionary with mainFile or file fields

        Returns:
            Tuple of (extraction_result, pdf_url)
        """
        # Find PDF URL
        pdf_url = None

        # Try mainFile first
        if 'mainFile' in paper and isinstance(paper['mainFile'], dict):
            pdf_url = paper['mainFile'].get('accessUrl')

        # Fallback to first file
        elif 'file' in paper and isinstance(paper['file'], list) and paper['file']:
            pdf_url = paper['file'][0].get('accessUrl')

        if not pdf_url:
            logger.debug(f"No PDF URL found for paper {paper.get('id')}")
            no_url_result = PDFExtractionResult(
                url="<no-url>",
                success=False,
                error="No PDF URL found in paper"
            )
            return no_url_result, None

        # Extract text
        result = self.extract_from_url(pdf_url)
        return result, pdf_url

    def extract_batch(
        self,
        papers: List[Dict[str, Any]],
        max_workers: int = 5,
        delay_between_downloads: float = 0.5
    ) -> List[PDFExtractionResult]:
        """
        Extract text from multiple papers in parallel.

        Args:
            papers: List of OParl paper objects
            max_workers: Maximum parallel download workers
            delay_between_downloads: Delay in seconds between downloads

        Returns:
            List of PDFExtractionResult objects

        Example:
            results = extractor.extract_batch(papers, max_workers=3)
            for result in results:
                if result.success:
                    print(f"{result.url}: {len(result.text)} chars")
        """
        results = []

        def process_paper(paper: Dict[str, Any]) -> PDFExtractionResult:
            """Process single paper."""
            time.sleep(delay_between_downloads)  # Be nice to the server

            result, pdf_url = self.extract_from_paper(paper)
            return result

        logger.info(f"Starting batch extraction for {len(papers)} papers")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_paper, paper): i
                for i, paper in enumerate(papers)
            }

            for future in as_completed(futures):
                idx = futures[future]
                try:
                    result = future.result()
                    results.append(result)

                    if (idx + 1) % 10 == 0:
                        logger.info(f"Processed {idx + 1}/{len(papers)} papers")

                except Exception as e:
                    logger.error(f"Error processing paper {idx}: {e}")
                    # Add placeholder for failed extraction
                    results.append(PDFExtractionResult(
                        url=papers[idx].get('id', '<unknown>'),
                        success=False,
                        error=str(e)
                    ))

        logger.info(f"Batch extraction complete: {len(results)} papers processed")
        return results

    def close(self):
        """Close the session and clean up resources."""
        self.session.close()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Standalone function for simple use cases
def extract_text_from_pdf_url(url: str, timeout: int = 60) -> PDFExtractionResult:
    """
    Simple function to extract text from a PDF URL.

    Args:
        url: PDF URL
        timeout: Download timeout

    Returns:
        PDFExtractionResult object

    Example:
        result = extract_text_from_pdf_url("https://example.com/doc.pdf")
        if result.success:
            print(result.text)
    """
    extractor = PDFExtractor(timeout=timeout)
    try:
        return extractor.extract_from_url(url)
    finally:
        extractor.close()
