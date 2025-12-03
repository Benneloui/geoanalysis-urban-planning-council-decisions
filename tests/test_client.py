"""
Unit tests for client.py - OParl API Client
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import requests
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from client import OParlClient


class TestOParlClient:
    """Test cases for OParlClient"""

    def test_init_with_config(self, mock_config, temp_dir):
        """Test client initialization with config"""
        mock_config['storage']['base_path'] = str(temp_dir)
        mock_config['project'] = {'city': 'augsburg'}
        mock_config['oparl']['endpoints'] = {'augsburg': 'https://api.example.org/oparl'}
        mock_config['oparl']['start_date'] = '2023-01-01T00:00:00Z'
        mock_config['oparl']['http_timeout_sec'] = 40

        client = OParlClient(mock_config)

        assert client.city == 'augsburg'
        assert client.timeout == 40
        assert client.system_url is not None

    def test_init_without_config(self):
        """Test client initialization without proper config structure"""
        # Missing required keys will cause ValueError
        with pytest.raises((ValueError, KeyError)):
            client = OParlClient({})

    @patch('requests.Session.get')
    def test_fetch_json_success(self, mock_get, mock_config, temp_dir):
        """Test successful JSON fetch"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # Mock successful response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'data': 'test'}
        mock_get.return_value = mock_response

        result = client._get_json('https://api.example.org/test')

        assert result == {'data': 'test'}
        mock_get.assert_called_once()

    @patch('requests.Session.get')
    def test_fetch_json_retry_on_failure(self, mock_get, mock_config, temp_dir):
        """Test retry mechanism on failure"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # First call fails, second succeeds
        mock_response_fail = Mock()
        mock_response_fail.status_code = 500
        def raise_error():
            raise requests.HTTPError("500 Server Error")
        mock_response_fail.raise_for_status = raise_error

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'test'}
        mock_response_success.raise_for_status = Mock()  # Success doesn't raise

        mock_get.side_effect = [mock_response_fail, mock_response_success]

        result = client._get_json('https://api.example.org/test')

        # Should succeed on second attempt
        assert result == {'data': 'test'}
        assert mock_get.call_count == 2

    @patch('requests.Session.get')
    def test_fetch_json_max_retries(self, mock_get, mock_config, temp_dir):
        """Test max retries exceeded"""
        mock_config['storage']['base_path'] = str(temp_dir)
        mock_config['oparl']['retry_count'] = 2
        client = OParlClient(mock_config)

        # All calls fail
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.HTTPError()
        mock_get.return_value = mock_response

        with pytest.raises(Exception):
            result = client._get_json('https://api.example.org/test')

    @patch('requests.Session.get')
    def test_fetch_papers_generator(self, mock_get, mock_config, temp_dir, mock_paper):
        """Test that fetch_papers works as generator"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # Mock system response
        mock_system_response = Mock()
        mock_system_response.status_code = 200
        mock_system_response.json.return_value = {
            'body': 'https://api.example.org/bodies'
        }

        # Mock bodies list response
        mock_bodies_response = Mock()
        mock_bodies_response.status_code = 200
        mock_bodies_response.json.return_value = {
            'data': [{'id': 'https://api.example.org/body/1', 'name': 'Test Body'}]
        }

        # Mock individual body object response
        mock_body_detail = Mock()
        mock_body_detail.status_code = 200
        mock_body_detail.json.return_value = {
            'id': 'https://api.example.org/body/1',
            'name': 'Test Body',
            'paper': 'https://api.example.org/papers'
        }

        page1 = {
            'data': [mock_paper],
            'links': {
                'next': 'https://api.example.org/papers?page=2'
            }
        }
        page2 = {
            'data': [mock_paper],
            'links': {}
        }

        mock_response1 = Mock()
        mock_response1.status_code = 200
        mock_response1.json.return_value = page1

        mock_response2 = Mock()
        mock_response2.status_code = 200
        mock_response2.json.return_value = page2

        mock_get.side_effect = [mock_system_response, mock_bodies_response, mock_body_detail, mock_response1, mock_response2]

        papers = list(client.fetch_papers())

        assert len(papers) == 2
        assert papers[0]['id'] == mock_paper['id']

    def test_generate_uri(self, mock_config, temp_dir):
        """Test URI generation"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        uri = client.generate_uri('paper', '123')

        assert 'paper' in uri
        assert '123' in uri
        assert uri.startswith('http')

    @patch('requests.Session.get')
    def test_fetch_meetings(self, mock_get, mock_config, temp_dir, mock_meeting):
        """Test fetch_meetings function"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # Mock system response
        mock_system_response = Mock()
        mock_system_response.status_code = 200
        mock_system_response.json.return_value = {
            'body': 'https://api.example.org/bodies'
        }

        # Mock bodies list response
        mock_bodies_response = Mock()
        mock_bodies_response.status_code = 200
        mock_bodies_response.json.return_value = {
            'data': [{'id': 'https://api.example.org/body/1', 'name': 'Test Body'}]
        }

        # Mock individual body object response
        mock_body_detail = Mock()
        mock_body_detail.status_code = 200
        mock_body_detail.json.return_value = {
            'id': 'https://api.example.org/body/1',
            'name': 'Test Body',
            'meeting': 'https://api.example.org/meetings'
        }

        mock_meetings_response = Mock()
        mock_meetings_response.status_code = 200
        mock_meetings_response.json.return_value = {
            'data': [mock_meeting],
            'links': {}
        }
        mock_get.side_effect = [mock_system_response, mock_bodies_response, mock_body_detail, mock_meetings_response]

        meetings = list(client.fetch_meetings())

        assert len(meetings) == 1
        assert meetings[0]['id'] == mock_meeting['id']

    @patch('requests.Session.get')
    def test_fetch_with_date_filter(self, mock_get, mock_config, temp_dir, mock_paper):
        """Test fetching with date range filter"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # Mock system response
        mock_system_response = Mock()
        mock_system_response.status_code = 200
        mock_system_response.json.return_value = {
            'body': 'https://api.example.org/bodies'
        }

        # Mock bodies list response
        mock_bodies_response = Mock()
        mock_bodies_response.status_code = 200
        mock_bodies_response.json.return_value = {
            'data': [{'id': 'https://api.example.org/body/1', 'name': 'Test Body'}]
        }

        # Mock individual body object response
        mock_body_detail = Mock()
        mock_body_detail.status_code = 200
        mock_body_detail.json.return_value = {
            'id': 'https://api.example.org/body/1',
            'name': 'Test Body',
            'paper': 'https://api.example.org/papers'
        }

        mock_papers_response = Mock()
        mock_papers_response.status_code = 200
        mock_papers_response.json.return_value = {
            'data': [mock_paper],
            'links': {}
        }
        mock_get.side_effect = [mock_system_response, mock_bodies_response, mock_body_detail, mock_papers_response]

        papers = list(client.fetch_papers(
            start_date='2024-01-01T00:00:00Z',
            end_date='2024-12-31T23:59:59Z'
        ))

        assert len(papers) == 1
        # Verify date parameters were included in request
        call_args = mock_get.call_args
        assert 'modified_since' in str(call_args) or 'params' in call_args[1]


class TestOParlClientIntegration:
    """Integration tests with real API (optional - requires network)"""

    @pytest.mark.skip(reason="Requires network access")
    def test_real_api_connection(self, mock_config, temp_dir):
        """Test connection to real OParl API"""
        mock_config['storage']['base_path'] = str(temp_dir)
        mock_config['oparl']['system_url'] = 'https://ris.augsburg.de/oparl/v1.1'

        client = OParlClient(mock_config)

        # Fetch one paper
        papers = list(client.fetch_papers(limit=1))

        assert len(papers) > 0
        assert 'id' in papers[0]
        assert 'type' in papers[0]
