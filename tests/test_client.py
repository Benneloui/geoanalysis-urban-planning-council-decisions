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
        client = OParlClient(mock_config)

        assert client.system_url == mock_config['oparl']['system_url']
        assert client.timeout == mock_config['oparl']['timeout']
        assert client.retry_count == mock_config['oparl']['retry_count']

    def test_init_without_config(self):
        """Test client initialization without config"""
        with pytest.raises((FileNotFoundError, KeyError)):
            OParlClient()

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

        result = client._fetch_json('https://api.example.org/test')

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
        mock_response_fail.raise_for_status.side_effect = requests.HTTPError()

        mock_response_success = Mock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {'data': 'test'}

        mock_get.side_effect = [mock_response_fail, mock_response_success]

        result = client._fetch_json('https://api.example.org/test')

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

        result = client._fetch_json('https://api.example.org/test')

        assert result is None
        assert mock_get.call_count == 2

    @patch('requests.Session.get')
    def test_fetch_papers_generator(self, mock_get, mock_config, temp_dir, mock_paper):
        """Test fetch_papers generator function"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        # Mock paginated response
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

        mock_get.side_effect = [mock_response1, mock_response2]

        papers = list(client.fetch_papers(body_id='https://api.example.org/body/1'))

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

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [mock_meeting],
            'links': {}
        }
        mock_get.return_value = mock_response

        meetings = list(client.fetch_meetings(
            organization_id='https://api.example.org/organization/1'
        ))

        assert len(meetings) == 1
        assert meetings[0]['id'] == mock_meeting['id']

    @patch('requests.Session.get')
    def test_fetch_with_date_filter(self, mock_get, mock_config, temp_dir, mock_paper):
        """Test fetching with date range filter"""
        mock_config['storage']['base_path'] = str(temp_dir)
        client = OParlClient(mock_config)

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'data': [mock_paper],
            'links': {}
        }
        mock_get.return_value = mock_response

        papers = list(client.fetch_papers(
            body_id='https://api.example.org/body/1',
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 12, 31)
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
