"""
Unit tests for extraction.py - PDF Text Extraction
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from extraction import PDFExtractor, PDFExtractionResult


class TestPDFExtractor:
    """Test cases for PDFExtractor"""

    def test_init(self, mock_config):
        """Test extractor initialization"""
        extractor = PDFExtractor(mock_config)

        assert extractor.timeout == mock_config['extraction']['timeout']
        assert extractor.use_ocr == mock_config['extraction']['use_ocr']

    @patch('requests.get')
    @patch('fitz.open')
    def test_extract_from_url_pymupdf_success(self, mock_fitz_open, mock_requests_get,
                                               mock_config, mock_pdf_text):
        """Test successful extraction with PyMuPDF"""
        extractor = PDFExtractor(mock_config)

        # Mock HTTP response
        mock_response = Mock()
        mock_response.content = b'fake-pdf-content'
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Mock PyMuPDF document
        mock_page = Mock()
        mock_page.get_text.return_value = mock_pdf_text

        mock_doc = Mock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = None

        mock_fitz_open.return_value = mock_doc

        result = extractor.extract_from_url('https://example.org/test.pdf')

        assert result.success is True
        assert result.text == mock_pdf_text
        assert result.method == 'pymupdf'
        assert result.page_count == 1

    @patch('requests.get')
    def test_extract_from_url_http_error(self, mock_requests_get, mock_config):
        """Test handling of HTTP errors"""
        extractor = PDFExtractor(mock_config)

        # Mock failed HTTP response
        mock_response = Mock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = Exception("Not Found")
        mock_requests_get.return_value = mock_response

        result = extractor.extract_from_url('https://example.org/nonexistent.pdf')

        assert result.success is False
        assert result.text == ""
        assert "error" in result.error.lower() or "not found" in result.error.lower()

    @patch('requests.get')
    @patch('fitz.open')
    def test_extract_from_url_empty_pdf(self, mock_fitz_open, mock_requests_get, mock_config):
        """Test handling of empty PDFs"""
        extractor = PDFExtractor(mock_config)

        mock_response = Mock()
        mock_response.content = b'fake-pdf-content'
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # Mock empty PyMuPDF document
        mock_page = Mock()
        mock_page.get_text.return_value = ""

        mock_doc = Mock()
        mock_doc.__len__.return_value = 1
        mock_doc.__getitem__.return_value = mock_page
        mock_doc.__enter__.return_value = mock_doc
        mock_doc.__exit__.return_value = None

        mock_fitz_open.return_value = mock_doc

        result = extractor.extract_from_url('https://example.org/empty.pdf')

        # Should try fallback to pdfplumber
        assert result is not None

    @patch('requests.get')
    @patch('fitz.open')
    @patch('pdfplumber.open')
    def test_extract_fallback_to_pdfplumber(self, mock_pdfplumber_open,
                                            mock_fitz_open, mock_requests_get,
                                            mock_config, mock_pdf_text):
        """Test fallback to pdfplumber when PyMuPDF fails"""
        extractor = PDFExtractor(mock_config)

        mock_response = Mock()
        mock_response.content = b'fake-pdf-content'
        mock_response.status_code = 200
        mock_requests_get.return_value = mock_response

        # PyMuPDF fails
        mock_fitz_open.side_effect = Exception("PyMuPDF error")

        # pdfplumber succeeds
        mock_page = Mock()
        mock_page.extract_text.return_value = mock_pdf_text

        mock_pdf = Mock()
        mock_pdf.pages = [mock_page]
        mock_pdf.__enter__.return_value = mock_pdf
        mock_pdf.__exit__.return_value = None

        mock_pdfplumber_open.return_value = mock_pdf

        result = extractor.extract_from_url('https://example.org/test.pdf')

        assert result.success is True
        assert result.text == mock_pdf_text
        assert result.method == 'pdfplumber'

    def test_extract_batch(self, mock_config, mock_paper):
        """Test batch extraction"""
        extractor = PDFExtractor(mock_config)

        papers = [mock_paper, mock_paper.copy()]

        with patch.object(extractor, 'extract_from_url') as mock_extract:
            mock_extract.return_value = PDFExtractionResult(
                url='https://example.org/test.pdf',
                success=True,
                text='Test content',
                method='pymupdf',
                page_count=1
            )

            results = extractor.extract_batch(papers)

            assert len(results) == 2
            assert all(r.success for r in results)

    def test_extraction_result_dataclass(self):
        """Test PDFExtractionResult dataclass"""
        result = PDFExtractionResult(
            url='https://example.org/test.pdf',
            success=True,
            text='Test content',
            method='pymupdf',
            page_count=5,
            file_size_kb=1024.5
        )

        assert result.url == 'https://example.org/test.pdf'
        assert result.success is True
        assert result.text == 'Test content'
        assert result.method == 'pymupdf'
        assert result.page_count == 5
        assert result.file_size_kb == 1024.5
        assert result.error is None

    @patch('requests.get')
    def test_extract_timeout(self, mock_requests_get, mock_config):
        """Test timeout handling"""
        mock_config['extraction']['timeout'] = 1
        extractor = PDFExtractor(mock_config)

        # Mock timeout
        mock_requests_get.side_effect = TimeoutError("Request timeout")

        result = extractor.extract_from_url('https://example.org/slow.pdf')

        assert result.success is False
        assert "timeout" in result.error.lower()


class TestPDFExtractionIntegration:
    """Integration tests for PDF extraction"""

    @pytest.mark.skip(reason="Requires network access and real PDF")
    def test_real_pdf_extraction(self, mock_config):
        """Test extraction from real PDF URL"""
        extractor = PDFExtractor(mock_config)

        # Use a known public PDF
        url = 'https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf'

        result = extractor.extract_from_url(url)

        assert result.success is True
        assert len(result.text) > 0
        assert result.page_count > 0
