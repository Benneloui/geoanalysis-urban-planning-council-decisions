"""Pytest configuration and shared fixtures"""
import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

@pytest.fixture
def temp_dir():
    """Create a temporary directory for test outputs"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)

@pytest.fixture
def mock_config():
    """Mock configuration for testing"""
    return {
        'project': {
            'name': 'Test OParl Pipeline',
            'city': 'augsburg',
            'version': '0.1'
        },
        'oparl': {
            'endpoints': {
                'augsburg': 'https://api.oparl.org/v1.1/system'
            },
            'system_url': 'https://api.oparl.org/v1.1',
            'start_date': '2023-01-01T00:00:00Z',
            'end_date': '2025-12-31T23:59:59Z',
            'http_timeout_sec': 40,
            'retry_attempts': 5,
            'retry_pause_sec': 2,
            'max_pages_meetings': 50,
            'timeout': 30,
            'retry_count': 3,
            'rate_limit': 10
        },
        'extraction': {
            'batch_size': 10,
            'timeout': 30,
            'use_ocr': False,
            'languages': ['deu', 'eng']
        },
        'geocoding': {
            'service': 'nominatim',
            'user_agent': 'geomodelierung-test',
            'timeout': 10,
            'rate_limit': 1,
            'cache_file': 'geocoding_cache_test.json'
        },
        'storage': {
            'base_path': 'data',
            'parquet': {
                'partition_cols': ['city', 'year'],
                'compression': 'snappy'
            },
            'rdf': {
                'format': 'turtle',
                'namespace': 'http://example.org/oparl/'
            }
        }
    }

@pytest.fixture
def mock_paper():
    """Mock OParl Paper object"""
    return {
        'id': 'https://api.example.org/paper/123',
        'type': 'https://schema.oparl.org/1.1/Paper',
        'name': 'Test Bebauungsplan',
        'reference': 'B-Plan 2024/01',
        'date': '2024-01-15',
        'created': '2024-01-10T10:00:00Z',
        'modified': '2024-01-15T14:30:00Z',
        'paperType': 'Beschlussvorlage',
        'mainFile': {
            'id': 'https://api.example.org/file/456',
            'name': 'Beschlussvorlage.pdf',
            'accessUrl': 'https://example.org/documents/test.pdf',
            'mimeType': 'application/pdf'
        },
        'auxiliaryFile': [],
        'consultation': [],
        'body': {
            'id': 'https://api.example.org/body/1',
            'name': 'Stadtrat Augsburg'
        }
    }

@pytest.fixture
def mock_meeting():
    """Mock OParl Meeting object"""
    return {
        'id': 'https://api.example.org/meeting/789',
        'type': 'https://schema.oparl.org/1.1/Meeting',
        'name': 'Stadtratssitzung',
        'start': '2024-01-15T18:00:00Z',
        'end': '2024-01-15T21:00:00Z',
        'location': {
            'description': 'Rathaus Augsburg'
        },
        'organization': [{
            'id': 'https://api.example.org/organization/1',
            'name': 'Stadtrat'
        }],
        'agendaItem': []
    }

@pytest.fixture
def mock_pdf_text():
    """Mock extracted PDF text"""
    return """
Bebauungsplan Nr. 2024/01
Sanierungsgebiet Maximilianstraße

Das Plangebiet liegt im Zentrum von Augsburg zwischen der
Maximilianstraße und dem Königsplatz. Die Sanierung umfasst
das Gebiet zwischen Grottenau und der Konrad-Adenauer-Allee.

Flurstücke: 123/4, 123/5, 124/1
Gemarkung: Augsburg

Beschluss gefasst am 15.01.2024
"""

@pytest.fixture
def mock_location():
    """Mock extracted location with geocoding"""
    return {
        'text': 'Maximilianstraße',
        'type': 'street',
        'confidence': 0.95,
        'context': 'Sanierungsgebiet Maximilianstraße',
        'coordinates': {
            'lat': 48.3689,
            'lon': 10.8978
        },
        'address': {
            'street': 'Maximilianstraße',
            'city': 'Augsburg',
            'postcode': '86150',
            'country': 'Deutschland'
        },
        'geocoding_method': 'nominatim',
        'geocoding_date': '2024-01-20'
    }

@pytest.fixture
def sample_rdf_graph():
    """Sample RDF graph for testing"""
    from rdflib import Graph, URIRef, Literal
    from rdflib.namespace import RDF, DCTERMS, GEO

    g = Graph()
    paper = URIRef("http://example.org/paper/123")
    g.add((paper, RDF.type, URIRef("https://schema.oparl.org/1.1/Paper")))
    g.add((paper, DCTERMS.title, Literal("Test Paper")))

    return g
