"""
Unit tests for spatial.py - Location Extraction and Geocoding
"""
import pytest
from unittest.mock import Mock, patch
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from spatial import SpatialProcessor


class TestSpatialProcessor:
    """Test cases for SpatialProcessor"""

    def test_init(self, mock_config):
        """Test processor initialization"""
        processor = SpatialProcessor(mock_config)

        assert processor.user_agent == mock_config['geocoding']['user_agent']
        assert processor.cache is not None

    def test_extract_locations_from_text(self, mock_config, mock_pdf_text):
        """Test location extraction from text"""
        processor = SpatialProcessor(mock_config)

        locations = processor.extract_locations(
            mock_pdf_text,
            paper_id='https://api.example.org/paper/123'
        )

        # Should find some locations
        assert len(locations) > 0
        # Should have paper_id attached
        assert all('paper_id' in loc for loc in locations)

    def test_extract_locations_empty_text(self, mock_config):
        """Test location extraction from empty text"""
        processor = SpatialProcessor(mock_config)

        locations = processor.extract_locations(
            "",
            paper_id='https://api.example.org/paper/123'
        )

        assert len(locations) == 0

    def test_extract_street_patterns(self, mock_config):
        """Test street name pattern extraction"""
        processor = SpatialProcessor(mock_config)

        text = "Die Sanierung der Maximilianstraße und Konrad-Adenauer-Allee"
        locations = processor.extract_locations(text, paper_id='test')

        # Should find street names
        street_locations = [loc for loc in locations if loc.get('type') == 'street']
        assert len(street_locations) > 0

    def test_extract_bplan_patterns(self, mock_config):
        """Test B-Plan pattern extraction"""
        processor = SpatialProcessor(mock_config)

        text = "Bebauungsplan Nr. 2024/01 für das Gebiet westlich der Innenstadt"
        locations = processor.extract_locations(text, paper_id='test')

        # Should find B-Plan reference
        bplan_locations = [loc for loc in locations if 'bplan' in loc.get('type', '').lower()]
        assert len(bplan_locations) > 0

    def test_extract_flurstueck_patterns(self, mock_config):
        """Test Flurstück pattern extraction"""
        processor = SpatialProcessor(mock_config)

        text = "Flurstück 123/4 in der Gemarkung Augsburg"
        locations = processor.extract_locations(text, paper_id='test')

        # Should find Flurstück
        flurstueck_locs = [loc for loc in locations if 'flur' in loc.get('type', '').lower()]
        assert len(flurstueck_locs) > 0

    @patch('geopy.geocoders.Nominatim.geocode')
    def test_geocode_location_success(self, mock_geocode, mock_config):
        """Test successful geocoding"""
        processor = SpatialProcessor(mock_config)

        # Mock geocoding result
        mock_result = Mock()
        mock_result.latitude = 48.3689
        mock_result.longitude = 10.8978
        mock_result.raw = {
            'address': {
                'road': 'Maximilianstraße',
                'city': 'Augsburg',
                'postcode': '86150'
            }
        }
        mock_geocode.return_value = mock_result

        location = {
            'text': 'Maximilianstraße',
            'type': 'street'
        }

        geocoded = processor._geocode_location(location, 'augsburg')

        assert geocoded is not None
        assert 'coordinates' in geocoded
        assert geocoded['coordinates']['lat'] == 48.3689
        assert geocoded['coordinates']['lon'] == 10.8978

    @patch('geopy.geocoders.Nominatim.geocode')
    def test_geocode_location_failure(self, mock_geocode, mock_config):
        """Test geocoding failure"""
        processor = SpatialProcessor(mock_config)

        # Mock failed geocoding
        mock_geocode.return_value = None

        location = {
            'text': 'Nonexistent Street',
            'type': 'street'
        }

        geocoded = processor._geocode_location(location, 'augsburg')

        # Should return original location without coordinates
        assert geocoded is not None
        assert 'coordinates' not in geocoded

    def test_geocode_batch(self, mock_config):
        """Test batch geocoding"""
        processor = SpatialProcessor(mock_config)

        locations = [
            {'text': 'Maximilianstraße', 'type': 'street'},
            {'text': 'Königsplatz', 'type': 'place'}
        ]

        with patch.object(processor, '_geocode_location') as mock_geocode:
            mock_geocode.return_value = {
                'text': 'Test',
                'type': 'street',
                'coordinates': {'lat': 48.0, 'lon': 11.0}
            }

            geocoded = processor.geocode_batch(locations, 'augsburg')

            assert len(geocoded) == 2
            assert mock_geocode.call_count == 2

    def test_geocoding_cache(self, mock_config, temp_dir):
        """Test geocoding cache functionality"""
        mock_config['geocoding']['cache_file'] = str(temp_dir / 'cache.json')
        processor = SpatialProcessor(mock_config)

        location = {
            'text': 'Maximilianstraße',
            'type': 'street',
            'coordinates': {'lat': 48.0, 'lon': 11.0}
        }

        # Save to cache
        processor._save_to_cache('maximilianstraße-augsburg', location)

        # Load from cache
        cached = processor._load_from_cache('maximilianstraße-augsburg')

        assert cached is not None
        assert cached['coordinates']['lat'] == 48.0

    def test_enrich_papers_with_locations(self, mock_config, mock_paper, mock_pdf_text):
        """Test enriching papers with extracted locations"""
        processor = SpatialProcessor(mock_config)

        papers = [{
            **mock_paper,
            'pdf_text': mock_pdf_text,
            'city': 'augsburg'
        }]

        with patch.object(processor, 'extract_locations') as mock_extract:
            mock_extract.return_value = [
                {'text': 'Maximilianstraße', 'type': 'street'}
            ]

            enriched = processor.enrich_papers_with_locations(papers)

            assert len(enriched) == 1
            assert 'locations' in enriched[0]

    def test_pdf_url_tracking(self, mock_config, mock_paper):
        """Test that pdf_url is tracked through extraction"""
        processor = SpatialProcessor(mock_config)

        pdf_url = mock_paper['mainFile']['accessUrl']
        text = "Sanierung der Maximilianstraße"

        locations = processor.extract_locations(
            text,
            paper_id=mock_paper['id'],
            pdf_url=pdf_url
        )

        # All locations should have pdf_url
        assert all('pdf_url' in loc for loc in locations)
        assert all(loc['pdf_url'] == pdf_url for loc in locations)


class TestSpatialProcessorIntegration:
    """Integration tests for spatial processing"""

    @pytest.mark.skip(reason="Requires network for geocoding")
    def test_real_geocoding(self, mock_config):
        """Test real geocoding with Nominatim"""
        processor = SpatialProcessor(mock_config)

        location = {
            'text': 'Maximilianstraße',
            'type': 'street'
        }

        geocoded = processor._geocode_location(location, 'Augsburg')

        assert geocoded is not None
        assert 'coordinates' in geocoded
        assert geocoded['coordinates']['lat'] > 0
        assert geocoded['coordinates']['lon'] > 0

    @pytest.mark.skip(reason="Requires spacy model")
    def test_ner_extraction(self, mock_config):
        """Test NER-based location extraction"""
        processor = SpatialProcessor(mock_config)

        text = """
        Der Stadtrat beschließt die Sanierung der Maximilianstraße
        zwischen Fuggerstraße und Ulrichsplatz in Augsburg.
        """

        locations = processor.extract_locations(text, paper_id='test')

        # Should find multiple location mentions
        assert len(locations) > 0
        assert any('maximilianstraße' in loc['text'].lower() for loc in locations)
