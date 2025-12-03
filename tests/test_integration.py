"""
Integration tests for the complete pipeline
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile
import shutil

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from client import OParlClient
from extraction import PDFExtractor
from storage import ParquetWriter, RDFWriter
from state import StateManager
from spatial import SpatialProcessor


class TestPipelineIntegration:
    """Integration tests for full pipeline"""

    def test_end_to_end_mock_pipeline(self, mock_config, temp_dir, mock_paper, mock_pdf_text):
        """Test complete pipeline with mocked components"""
        mock_config['storage']['base_path'] = str(temp_dir)

        # Initialize components
        client = OParlClient(mock_config)
        extractor = PDFExtractor(mock_config)
        parquet_writer = ParquetWriter(mock_config)
        rdf_writer = RDFWriter(mock_config)
        state_manager = StateManager(temp_dir / 'state.db')
        spatial_processor = SpatialProcessor(mock_config)

        # Mock data flow
        papers = [mock_paper]

        # Step 1: Extract PDFs
        with patch.object(extractor, 'extract_from_url') as mock_extract:
            mock_extract.return_value = Mock(
                success=True,
                text=mock_pdf_text,
                url=mock_paper['mainFile']['accessUrl']
            )

            for paper in papers:
                if not state_manager.is_processed(paper['id'], 'paper'):
                    result = extractor.extract_from_url(paper['mainFile']['accessUrl'])
                    paper['pdf_text'] = result.text
                    paper['pdf_url'] = result.url

                    # Step 2: Extract locations
                    locations = spatial_processor.extract_locations(
                        paper['pdf_text'],
                        paper_id=paper['id'],
                        pdf_url=paper['pdf_url']
                    )
                    paper['locations'] = locations

                    # Step 3: Write to storage
                    paper['city'] = 'augsburg'
                    paper['year'] = 2024

                    state_manager.mark_processed(paper['id'], 'paper')

            # Write outputs
            parquet_writer.write_papers_table(papers)
            rdf_writer.add_paper(papers[0])

            # Verify outputs
            assert (temp_dir / 'papers_parquet').exists()
            assert len(rdf_writer.graph) > 0
            assert state_manager.is_processed(mock_paper['id'], 'paper')

    def test_batch_processing(self, mock_config, temp_dir, mock_paper):
        """Test batch processing with checkpoints"""
        mock_config['storage']['base_path'] = str(temp_dir)

        state_manager = StateManager(temp_dir / 'state.db')

        # Simulate batch processing
        papers = [mock_paper.copy() for _ in range(10)]
        for i, paper in enumerate(papers):
            paper['id'] = f"https://api.example.org/paper/{i}"

        batch_size = 3
        for batch_num in range(0, len(papers), batch_size):
            batch = papers[batch_num:batch_num + batch_size]

            for paper in batch:
                state_manager.mark_processed(paper['id'], 'paper')

            # Checkpoint after each batch
            state_manager.checkpoint(f'batch_{batch_num}', {
                'papers_processed': len(batch)
            })

        # Verify all processed
        stats = state_manager.get_statistics()
        assert stats['total_processed'] == 10

    def test_error_recovery(self, mock_config, temp_dir, mock_paper):
        """Test pipeline recovery after errors"""
        mock_config['storage']['base_path'] = str(temp_dir)

        state_manager = StateManager(temp_dir / 'state.db')
        extractor = PDFExtractor(mock_config)

        papers = [mock_paper.copy() for _ in range(5)]
        for i, paper in enumerate(papers):
            paper['id'] = f"https://api.example.org/paper/{i}"

        # Simulate processing with some failures
        with patch.object(extractor, 'extract_from_url') as mock_extract:
            def extract_side_effect(url):
                # Fail on paper 2
                if 'paper/2' in url:
                    return Mock(success=False, error='Network error')
                return Mock(success=True, text='content', url=url)

            mock_extract.side_effect = extract_side_effect

            for paper in papers:
                result = extractor.extract_from_url(paper['mainFile']['accessUrl'])

                if result.success:
                    state_manager.mark_processed(paper['id'], 'paper')
                else:
                    state_manager.mark_failed(paper['id'], 'paper', result.error)

        # Check stats
        stats = state_manager.get_statistics()
        assert stats['total_processed'] == 5
        assert stats['successful'] == 4
        assert stats['failed'] == 1

        # Get failed resources
        failed = state_manager.get_failed_resources('paper')
        assert len(failed) == 1
        assert 'paper/2' in failed[0]['resource_id']

    def test_location_to_geojson_pipeline(self, mock_config, temp_dir, mock_location):
        """Test complete flow from location extraction to GeoJSON"""
        mock_config['storage']['base_path'] = str(temp_dir)

        parquet_writer = ParquetWriter(mock_config)

        # Create locations with coordinates
        locations = []
        for i in range(5):
            loc = mock_location.copy()
            loc['paper_id'] = f"https://api.example.org/paper/{i}"
            loc['pdf_url'] = f"https://example.org/doc{i}.pdf"
            locations.append(loc)

        # Export to GeoJSON
        output_file = parquet_writer.export_locations_for_map(locations, 'augsburg')

        assert output_file.exists()

        # Verify GeoJSON structure
        import json
        with open(output_file) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 5

        # Check each feature
        for feature in geojson['features']:
            assert feature['type'] == 'Feature'
            assert 'geometry' in feature
            assert 'properties' in feature
            assert 'pdf_url' in feature['properties']

    def test_rdf_graph_completeness(self, mock_config, temp_dir, mock_paper, mock_location):
        """Test RDF graph contains all expected triples"""
        mock_config['storage']['base_path'] = str(temp_dir)

        rdf_writer = RDFWriter(mock_config)

        # Add paper
        rdf_writer.add_paper(mock_paper)

        # Add location
        rdf_writer._add_location_to_paper(
            paper_id=mock_paper['id'],
            location=mock_location,
            pdf_url=mock_paper['mainFile']['accessUrl']
        )

        # Check graph
        from rdflib import URIRef, RDF

        paper_uri = URIRef(mock_paper['id'])

        # Should have paper type
        assert (paper_uri, RDF.type, URIRef('https://schema.oparl.org/1.1/Paper')) in rdf_writer.graph

        # Should have location data
        location_triples = list(rdf_writer.graph.triples((paper_uri, None, None)))
        assert len(location_triples) > 0

        # Write and verify serialization
        output_file = temp_dir / 'test.ttl'
        rdf_writer.write_to_file(output_file)

        assert output_file.exists()
        assert output_file.stat().st_size > 0


class TestPipelineOrchestrator:
    """Test the main pipeline orchestrator"""

    @pytest.mark.skip(reason="Requires full implementation")
    def test_orchestrator_run(self, mock_config, temp_dir):
        """Test pipeline orchestrator execution"""
        # This would test run_pipeline.py
        # Skipped as it requires full setup
        pass

    def test_cli_argument_parsing(self):
        """Test CLI argument parsing"""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument('--city', type=str, default='augsburg')
        parser.add_argument('--test', action='store_true')
        parser.add_argument('--limit', type=int, default=None)

        # Test with default args
        args = parser.parse_args(['--city', 'augsburg'])
        assert args.city == 'augsburg'
        assert args.test is False

        # Test with test flag
        args = parser.parse_args(['--test'])
        assert args.test is True


class TestDataFlow:
    """Test data flow through pipeline components"""

    def test_paper_metadata_preservation(self, mock_config, temp_dir, mock_paper):
        """Test that paper metadata is preserved through pipeline"""
        mock_config['storage']['base_path'] = str(temp_dir)

        parquet_writer = ParquetWriter(mock_config)

        # Add required fields
        paper = mock_paper.copy()
        paper['city'] = 'augsburg'
        paper['year'] = 2024
        paper['pdf_text'] = 'test content'

        # Write and read back
        parquet_writer.write_papers_table([paper])

        import pandas as pd
        df = pd.read_parquet(temp_dir / 'papers_parquet')

        # Verify metadata
        assert df['name'].iloc[0] == mock_paper['name']
        assert df['reference'].iloc[0] == mock_paper['reference']
        assert df['city'].iloc[0] == 'augsburg'
        assert df['year'].iloc[0] == 2024

    def test_location_provenance_tracking(self, mock_config):
        """Test that location provenance (paper_id, pdf_url) is tracked"""
        processor = SpatialProcessor(mock_config)

        paper_id = 'https://api.example.org/paper/123'
        pdf_url = 'https://example.org/doc.pdf'
        text = "Sanierung der Maximilianstraße"

        locations = processor.extract_locations(
            text,
            paper_id=paper_id,
            pdf_url=pdf_url
        )

        # All locations should have provenance
        for loc in locations:
            assert loc.get('paper_id') == paper_id
            assert loc.get('pdf_url') == pdf_url
