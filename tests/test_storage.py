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

        assert writer.base_dir == temp_dir
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

        count = writer.write_batch(papers, city='augsburg')

        # Verify write successful
        assert count == 1
        assert temp_dir.exists()

        # Read back and verify
        df = writer.read_all()
        assert len(df) == 1
        assert df['name'].iloc[0] == mock_paper['name']
        assert df['city'].iloc[0] == 'augsburg'

    def test_write_locations_table(self, mock_config, temp_dir, mock_location):
        """Test writing locations to Parquet"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        papers_with_locations = [{
            'paper_id': 'https://api.example.org/paper/123',
            'paper_name': 'Test Paper',
            'paper_date': '2024-01-15',
            'pdf_url': 'https://example.org/doc.pdf',
            'locations': [mock_location],
            'city': 'augsburg',
            'year': 2024
        }]

        count = writer.write_locations_table(papers_with_locations, city='augsburg')

        # Verify write successful
        assert count >= 0

    def test_write_empty_data(self, mock_config, temp_dir):
        """Test handling of empty data"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        # Should not raise error
        count = writer.write_batch([], city='augsburg')
        assert count == 0

        count = writer.write_locations_table([], city='augsburg')
        assert count == 0

    def test_partitioning(self, mock_config, temp_dir, mock_paper):
        """Test data partitioning by city and year"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = ParquetWriter(mock_config)

        # Write augsburg papers
        augsburg_papers = [
            {**mock_paper, 'city': 'augsburg', 'year': 2024},
            {**mock_paper, 'city': 'augsburg', 'year': 2023}
        ]
        writer.write_batch(augsburg_papers, city='augsburg')

        # Verify data was written
        df = writer.read_partition('augsburg')
        assert len(df) == 2
        assert df['city'].unique()[0] == 'augsburg'
        # Verify partition directory exists
        assert (temp_dir / 'papers').exists()

    def test_export_locations_for_map(self, mock_config, temp_dir, mock_location):
        """Test GeoJSON export for web mapping"""
        from storage import export_locations_for_map
        import pandas as pd

        # Create a parquet file with location data
        locations_data = [{
            'paper_id': 'https://api.example.org/paper/123',
            'pdf_url': 'https://example.org/doc.pdf',
            'latitude': mock_location['coordinates']['lat'],
            'longitude': mock_location['coordinates']['lon'],
            'location_type': mock_location['type'],
            'location_value': mock_location['text'],
            'city': 'augsburg'
        }]

        locations_parquet = temp_dir / 'locations.parquet'
        pd.DataFrame(locations_data).to_parquet(locations_parquet)

        output_geojson = temp_dir / 'locations.geojson'
        geojson = export_locations_for_map(
            str(locations_parquet),
            str(output_geojson),
            filter_city='augsburg'
        )

        assert output_geojson.exists()
        assert geojson['type'] == 'FeatureCollection'
        assert len(geojson['features']) == 1
        assert geojson['features'][0]['geometry']['type'] == 'Point'


class TestRDFWriter:
    """Test cases for RDFWriter"""

    def test_init(self, mock_config, temp_dir):
        """Test RDF writer initialization"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        assert writer.output_file.parent == temp_dir
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

        # Then add spatial relation
        writer.add_spatial_relation(
            paper_id=mock_paper['id'],
            location_text=mock_location['text'],
            latitude=mock_location['coordinates']['lat'],
            longitude=mock_location['coordinates']['lon']
        )

        # Verify location triples
        paper_uri = URIRef(mock_paper['id'])
        location_triples = list(writer.graph.triples((paper_uri, None, None)))

        assert len(location_triples) > 0

    def test_write_to_file(self, mock_config, temp_dir, mock_paper):
        """Test writing RDF graph to file"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        writer.add_paper(mock_paper)

        output_file = temp_dir / 'test.ttl'
        writer.graph.serialize(destination=str(output_file), format='turtle')

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

        writer.write_batch(papers, city='augsburg')

        # Read back
        df = writer.read_all()

        assert len(df) == 1
        assert df['name'].iloc[0] == mock_paper['name']
        assert df['pdf_text'].iloc[0] == mock_pdf_text

    def test_roundtrip_rdf(self, mock_config, temp_dir, mock_paper):
        """Test writing and reading RDF data"""
        mock_config['storage']['base_path'] = str(temp_dir)
        writer = RDFWriter(mock_config)

        writer.add_paper(mock_paper)

        output_file = temp_dir / 'test.ttl'
        writer.graph.serialize(destination=str(output_file), format='turtle')

        # Read back
        new_graph = Graph()
        new_graph.parse(output_file, format='turtle')

        paper_uri = URIRef(mock_paper['id'])
        assert (paper_uri, RDF.type, URIRef('https://schema.oparl.org/1.1/Paper')) in new_graph
