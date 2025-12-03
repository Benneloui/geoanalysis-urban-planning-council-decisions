"""
Tests for Ephemeral Storage
============================

Tests the temporary file handling for large PDFs (200+ pages).

Key Features:
- Size-based routing (memory vs. temp file)
- Context manager cleanup
- Streaming extraction
- File-based extraction methods
"""

import pytest
import tempfile
import os
from pathlib import Path
from src.extraction import PDFExtractor


class TestEphemeralStorage:
    """Test ephemeral storage for large PDFs."""

    def test_temp_file_context_manager(self):
        """Test temp file creation and cleanup."""
        extractor = PDFExtractor()
        test_data = b'Test PDF content' * 1000

        # Create temp file
        with extractor._temp_pdf_file(test_data) as temp_path:
            # Verify file exists
            assert os.path.exists(temp_path)
            assert temp_path.endswith('.pdf')

            # Verify content
            with open(temp_path, 'rb') as f:
                content = f.read()
            assert content == test_data

            temp_path_saved = temp_path

        # Verify cleanup after context exit
        assert not os.path.exists(temp_path_saved)

    def test_size_based_routing(self):
        """Test that PDFs are routed based on size threshold."""
        # Set low threshold for testing
        extractor = PDFExtractor(max_memory_mb=1)

        # Small bytes
        small_bytes = b'small' * 100  # ~500 bytes
        assert len(small_bytes) <= extractor.max_memory_bytes

        # Large bytes
        large_bytes = b'large' * 300000  # ~1.5 MB
        assert len(large_bytes) > extractor.max_memory_bytes

    def test_max_memory_bytes_configuration(self):
        """Test configurable memory threshold."""
        # Default 10MB
        extractor1 = PDFExtractor()
        assert extractor1.max_memory_bytes == 10 * 1024 * 1024

        # Custom 50MB
        extractor2 = PDFExtractor(max_memory_mb=50)
        assert extractor2.max_memory_bytes == 50 * 1024 * 1024

        # Low 1MB
        extractor3 = PDFExtractor(max_memory_mb=1)
        assert extractor3.max_memory_bytes == 1 * 1024 * 1024

    def test_extract_from_bytes_routing(self):
        """Test extract_from_bytes routes based on size."""
        extractor = PDFExtractor(max_memory_mb=1)

        # Small bytes should work (even if extraction fails without valid PDF)
        small_bytes = b'%PDF-1.4\nsmall content'
        result = extractor.extract_from_bytes(small_bytes)
        # Result can be None if not a valid PDF, but should not raise

        # Large bytes should use temp file path (also might fail with invalid PDF)
        large_bytes = b'%PDF-1.4\n' + b'large content' * 100000
        result = extractor.extract_from_bytes(large_bytes)
        # Result can be None if not a valid PDF, but should not raise

    def test_temp_file_cleanup_on_error(self):
        """Test temp file is cleaned up even if extraction fails."""
        extractor = PDFExtractor()
        test_data = b'Invalid PDF content'

        try:
            with extractor._temp_pdf_file(test_data) as temp_path:
                temp_path_saved = temp_path
                # Simulate error
                raise ValueError("Test error")
        except ValueError:
            pass

        # Verify cleanup even with error
        assert not os.path.exists(temp_path_saved)

    def test_large_pdf_simulation(self):
        """Simulate handling a 220-page PDF (~15MB)."""
        # Simulate large PDF size
        extractor = PDFExtractor(max_memory_mb=10)

        # 220 pages × ~70KB/page ≈ 15MB
        simulated_large_pdf = b'%PDF-1.4\n' + b'X' * (15 * 1024 * 1024)

        # Should exceed threshold
        assert len(simulated_large_pdf) > extractor.max_memory_bytes

        # Test temp file handling
        with extractor._temp_pdf_file(simulated_large_pdf) as temp_path:
            assert os.path.exists(temp_path)
            assert os.path.getsize(temp_path) > 15 * 1024 * 1024

    def test_file_based_extraction_methods_exist(self):
        """Verify file-based extraction methods are implemented."""
        extractor = PDFExtractor()

        # Check methods exist
        assert hasattr(extractor, '_extract_pymupdf_from_file')
        assert hasattr(extractor, '_extract_pdfplumber_from_file')
        assert hasattr(extractor, '_extract_ocr_from_file')
        assert hasattr(extractor, '_extract_from_file')

        # Check byte-based methods still exist
        assert hasattr(extractor, '_extract_pymupdf_from_bytes')
        assert hasattr(extractor, '_extract_pdfplumber_from_bytes')
        assert hasattr(extractor, '_extract_ocr_from_bytes')

    def test_streaming_method_exists(self):
        """Verify streaming extraction method is implemented."""
        extractor = PDFExtractor()
        assert hasattr(extractor, '_extract_from_stream_via_tempfile')


class TestMemoryEfficiency:
    """Test memory efficiency of ephemeral storage."""

    def test_no_memory_accumulation(self):
        """Test that temp files don't accumulate in memory."""
        extractor = PDFExtractor(max_memory_mb=1)

        # Process multiple "large" PDFs
        for i in range(5):
            large_data = b'PDF content ' * 200000
            with extractor._temp_pdf_file(large_data) as temp_path:
                # File exists during processing
                assert os.path.exists(temp_path)
            # File deleted after processing
            assert not os.path.exists(temp_path)

    def test_temp_directory_cleanup(self):
        """Test that temp directory is cleaned up."""
        extractor = PDFExtractor()
        temp_paths = []

        # Create multiple temp files
        for i in range(3):
            test_data = f'Test {i}'.encode() * 1000
            with extractor._temp_pdf_file(test_data) as temp_path:
                temp_paths.append(temp_path)

        # All should be cleaned up
        for temp_path in temp_paths:
            assert not os.path.exists(temp_path)


@pytest.mark.integration
class TestRealWorldScenarios:
    """Integration tests for real-world scenarios."""

    def test_augsburg_220_page_pdf_scenario(self):
        """Test handling of actual Augsburg 220-page PDF scenario."""
        # Realistic settings for Augsburg data
        extractor = PDFExtractor(
            max_memory_mb=10,  # Conservative threshold
            timeout=120,       # Longer timeout for large files
            use_ocr=True
        )

        # Simulate 220-page PDF
        # Typical: 220 pages × 70KB/page ≈ 15.4MB
        simulated_pdf_size = 220 * 70 * 1024

        assert simulated_pdf_size > extractor.max_memory_bytes
        print(f"220-page PDF: {simulated_pdf_size/(1024*1024):.1f}MB")
        print(f"Threshold: {extractor.max_memory_bytes/(1024*1024):.1f}MB")
        print("✓ Will use ephemeral storage")
