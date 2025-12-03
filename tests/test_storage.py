"""
Unit tests for storage.py - Parquet and RDF Writers
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import pandas as pd
from rdflib import Graph, URIRef, Literal
from rdflib.namespace import RDF, DCTERMS

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from storage import ParquetWriter, RDFWriter


class TestParquetWriter:
    """Test cases for ParquetWriter"""

    def test_init(self, mock_config, temp_dir):
        """Test writer initialization"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        assert writer.base_path == temp_dir
        assert writer.partition_cols == ['city', 'year']

    def test_write_papers_table(self, mock_config, temp_dir, mock_paper, mock_pdf_text):
        """Test writing papers to Parquet"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        papers = [{
            **mock_paper,
            'city': 'augsburg',
            'year': 2024,
            'pdf_text': mock_pdf_text
        }]

        writer.write_papers_table(papers)

        # Verify file was created
        output_dir = temp_dir / 'papers_parquet'
        assert output_dir.exists()

        # Read back and verify
        df = pd.read_parquet(output_dir)
        assert len(df) == 1
        assert df['name'].iloc[0] == mock_paper['name']
        assert df['city'].iloc[0] == 'augsburg'

    def test_write_locations_table(self, mock_config, temp_dir, mock_location):
        """Test writing locations to Parquet"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        locations = [{
            **mock_location,
            'paper_id': 'https://api.example.org/paper/123',
            'city': 'augsburg',
            'year': 2024
        }]

        writer.write_locations_table(locations)

        # Verify file was created
        output_dir = temp_dir / 'papers_parquet'
        assert output_dir.exists()

        # Read back and verify
        df = pd.read_parquet(output_dir)
        assert len(df) == 1
        assert df['text'].iloc[0] == mock_location['text']
        assert df['type'].iloc[0] == mock_location['type']

    def test_write_empty_data(self, mock_config, temp_dir):
        """Test handling of empty data"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        # Should not raise error
        writer.write_papers_table([])
        writer.write_locations_table([])

    def test_partitioning(self, mock_config, temp_dir, mock_paper):
        """Test data partitioning by city and year"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        papers = [
            {**mock_paper, 'city': 'augsburg', 'year': 2024},
            {**mock_paper, 'city': 'augsburg', 'year': 2023},
            {**mock_paper, 'city': 'munich', 'year': 2024}
        ]

        writer.write_papers_table(papers)

        # Verify partitions were created
        output_dir = temp_dir / 'papers_parquet'
        assert (output_dir / 'city=augsburg').exists()
        assert (output_dir / 'city=munich').exists()

    def test_export_locations_for_map(self, mock_config, temp_dir, mock_location):
        """Test GeoJSON export for web mapping"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        locations = [{
            **mock_location,
            'paper_id': 'https://api.example.org/paper/123',
            'pdf_url': 'https://example.org/doc.pdf'
        }]

        output_file = writer.export_locations_for_map(locations, 'augsburg')

        assert output_file.exists()
        assert output_file.name.endswith('.geojson')

        # Verify GeoJSON structure
        import json
        with open(output_file) as f:
            geojson = json.load(f)

        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 1
        assert geojson['features'][0]['geometry']['type'] == 'Point'


class TestRDFWriter:
    """Test cases for RDFWriter"""

    def test_init(self, mock_config, temp_dir):
        """Test RDF writer initialization"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        assert writer.base_path == temp_dir
        assert isinstance(writer.graph, Graph)

    def test_add_paper_to_graph(self, mock_config, temp_dir, mock_paper):
        """Test adding paper to RDF graph"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        writer.add_paper(mock_paper)

        # Verify triple was added
        paper_uri = URIRef(mock_paper['id'])
        assert (paper_uri, RDF.type, URIRef('https://schema.oparl.org/1.1/Paper')) in writer.graph
        assert len(list(writer.graph.triples((paper_uri, None, None)))) > 0

    def test_add_location_to_paper(self, mock_config, temp_dir, mock_paper, mock_location):
        """Test adding location to paper in RDF"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        # First add paper
        writer.add_paper(mock_paper)

        # Then add location
        writer._add_location_to_paper(
            paper_id=mock_paper['id'],
            location=mock_location,
            pdf_url=mock_paper['mainFile']['accessUrl']
        )

        # Verify location triples
        paper_uri = URIRef(mock_paper['id'])
        location_triples = list(writer.graph.triples((paper_uri, None, None)))

        assert len(location_triples) > 0
        # Check for geo coordinates
        assert any('geo' in str(pred).lower() for _, pred, _ in location_triples)

    def test_write_to_file(self, mock_config, temp_dir, mock_paper):
        """Test writing RDF graph to file"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        writer.add_paper(mock_paper)

        output_file = temp_dir / 'ttl' / 'test.ttl'
        writer.write_to_file(output_file)

        assert output_file.exists()

        # Verify file can be read back
        new_graph = Graph()
        new_graph.parse(output_file, format='turtle')
        assert len(new_graph) > 0

    def test_multiple_papers(self, mock_config, temp_dir, mock_paper):
        """Test adding multiple papers to graph"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        # Add multiple papers
        for i in range(3):
            paper = mock_paper.copy()
            paper['id'] = f"https://api.example.org/paper/{i}"
            writer.add_paper(paper)

        # Should have triples for all papers
        papers_count = len(list(writer.graph.subjects(RDF.type, URIRef('https://schema.oparl.org/1.1/Paper'))))
        assert papers_count == 3

    def test_serialize_formats(self, mock_config, temp_dir, mock_paper):
        """Test different RDF serialization formats"""
        mock_config['storage']['base_path'] = str(temp_dir)

        for fmt in ['turtle', 'n3', 'nt']:
            writer = RDFWriter(mock_config)
            writer.add_paper(mock_paper)

            output_file = temp_dir / f'test.{fmt}'
            writer.graph.serialize(destination=str(output_file), format=fmt)

            assert output_file.exists()
            assert output_file.stat().st_size > 0


class TestStorageIntegration:
    """Integration tests for storage components"""

    def test_roundtrip_parquet(self, mock_config, temp_dir, mock_paper, mock_pdf_text):
        """Test writing and reading Parquet data"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        papers = [{
            **mock_paper,
            'city': 'augsburg',
            'year': 2024,
            'pdf_text': mock_pdf_text
        }]

        writer.write_papers_table(papers)

        # Read back
        df = pd.read_parquet(temp_dir / 'papers_parquet')

        assert len(df) == 1
        assert df['name'].iloc[0] == mock_paper['name']
        assert df['pdf_text'].iloc[0] == mock_pdf_text

    def test_roundtrip_rdf(self, mock_config, temp_dir, mock_paper):
        """Test writing and reading RDF data"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        writer.add_paper(mock_paper)

        output_file = temp_dir / 'test.ttl'
        writer.write_to_file(output_file)

        # Read back
        new_graph = Graph()
        new_graph.parse(output_file, format='turtle')

        paper_uri = URIRef(mock_paper['id'])
        assert (paper_uri, RDF.type, URIRef('https://schema.oparl.org/1.1/Paper')) in new_graph
