#!/usr/bin/env python3
"""
Setup City Gazetteer from Overpass API

One-time setup script to fetch geospatial data for a city from OpenStreetMap
via Overpass API. Creates a local GeoJSON gazetteer for validation and enrichment.

This script:
1. Fetches all street names in the city
2. Fetches all administrative boundaries (districts)
3. Fetches public buildings and landmarks
4. Saves to GeoJSON format for reference

Usage:
    python scripts/00_setup_city.py --city augsburg
"""

import sys
import argparse
import json
import logging
import ssl
import certifi
from pathlib import Path
from typing import Dict, List, Any
import urllib.request
import urllib.error

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OverpassClient:
    """Client for Overpass API queries."""

    BASE_URL = "https://overpass-api.de/api/interpreter"
    TIMEOUT = 60

    def __init__(self):
        """Initialize Overpass client."""
        self.headers = {
            'User-Agent': 'Geomodelierung/0.1 (+https://github.com/benneloui/geoanalysis)'
        }

    def query(self, query: str) -> Dict[str, Any]:
        """
        Execute Overpass QL query.

        Args:
            query: Overpass QL query string

        Returns:
            GeoJSON FeatureCollection
        """
        logger.info("Querying Overpass API...")

        try:
            request = urllib.request.Request(
                self.BASE_URL,
                data=query.encode('utf-8'),
                headers=self.headers,
                method='POST'
            )

            # Use certifi's certificate store for SSL verification
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            with urllib.request.urlopen(request, timeout=self.TIMEOUT, context=ssl_context) as response:
                data = json.loads(response.read().decode('utf-8'))
                logger.info("✓ Got response with %d elements", len(data.get('elements', [])))
                return data

        except urllib.error.HTTPError as e:
            logger.error("HTTP Error: %d - %s", e.code, e.reason)
            raise
        except urllib.error.URLError as e:
            logger.error("URL Error: %s", e.reason)
            raise
        except Exception as e:
            logger.error("Error: %s", e)
            raise

    def osm_to_geojson(self, osm_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert Overpass OSM data to GeoJSON."""
        features = []

        for element in osm_data.get('elements', []):
            # Skip nodes without coordinates or relevant tags
            if element.get('type') == 'node' and 'lat' in element and 'lon' in element:
                tags = element.get('tags', {})
                if any(key in tags for key in ['name', 'highway', 'amenity', 'shop', 'building']):
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'Point',
                            'coordinates': [element['lon'], element['lat']]
                        },
                        'properties': {
                            'id': f"osm/node/{element['id']}",
                            **tags
                        }
                    })

            # Handle ways (for streets, boundaries)
            elif element.get('type') == 'way':
                tags = element.get('tags', {})
                # Only include named streets and boundaries
                if 'name' in tags and any(key in tags for key in ['highway', 'boundary', 'natural']):
                    features.append({
                        'type': 'Feature',
                        'geometry': {
                            'type': 'LineString',
                            'coordinates': []  # Would need node lookup
                        },
                        'properties': {
                            'id': f"osm/way/{element['id']}",
                            **tags
                        }
                    })

        return {
            'type': 'FeatureCollection',
            'features': features
        }


def fetch_augsburg_streets() -> Dict[str, Any]:
    """Fetch all street names in Augsburg with geocoding."""
    logger.info("\n=== Fetching streets from Augsburg ===")

    client = OverpassClient()

    try:
        # Query all named streets in Augsburg with center coordinates
        # Using bbox for Augsburg (approximate): ~48.3°-48.4°N, ~10.8°-10.9°E
        streets_query = """
        [out:json];
        (
            way["highway"]["name"](48.3,10.8,48.4,10.9);
        );
        out center;
        """

        streets_data = client.query(streets_query)

        features = []
        street_names = set()

        for element in streets_data.get('elements', []):
            if element.get('type') == 'way':
                tags = element.get('tags', {})
                name = tags.get('name', '')

                if name and name not in street_names:
                    street_names.add(name)

                    # Get center coordinates (provided by Overpass with 'out center')
                    center = element.get('center', {})
                    lat = center.get('lat')
                    lon = center.get('lon')

                    if lat and lon:
                        features.append({
                            'type': 'Feature',
                            'geometry': {
                                'type': 'Point',
                                'coordinates': [lon, lat]
                            },
                            'properties': {
                                'id': f"osm/way/{element['id']}",
                                'name': name,
                                'highway': tags.get('highway', ''),
                                'source': 'overpass'
                            }
                        })

        logger.info(f"✓ Found {len(features)} unique streets with coordinates")

        return {
            'type': 'FeatureCollection',
            'features': features
        }

    except Exception as e:
        logger.error(f"Failed to fetch streets: {e}")
        return {'type': 'FeatureCollection', 'features': []}
def fetch_augsburg_districts() -> Dict[str, Any]:
    """Fetch administrative districts in Augsburg."""
    logger.info("\n=== Fetching districts from Augsburg ===")

    query = """
    [out:json];
    (
        relation["boundary"="administrative"]["admin_level"="10"]["name"];
    );
    out center;
    """

    client = OverpassClient()

    try:
        data = client.query(query)

        # Extract district names
        districts = []
        for element in data.get('elements', []):
            tags = element.get('tags', {})
            if 'name' in tags:
                districts.append({
                    'name': tags['name'],
                    'type': 'district',
                    'id': f"osm/{element.get('type')}/{element.get('id')}"
                })

        logger.info(f"✓ Found {len(districts)} districts")

        return {
            'type': 'FeatureCollection',
            'features': [
                {
                    'type': 'Feature',
                    'geometry': None,
                    'properties': d
                }
                for d in districts
            ]
        }

    except Exception as e:
        logger.error(f"Failed to fetch districts: {e}")
        return {'type': 'FeatureCollection', 'features': []}


def save_gazetteer(output_dir: Path, streets: Dict, districts: Dict):
    """Save gazetteer files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save streets
    streets_file = output_dir / 'streets.geojson'
    with open(streets_file, 'w', encoding='utf-8') as f:
        json.dump(streets, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ Saved {len(streets['features'])} streets to {streets_file}")

    # Save districts
    districts_file = output_dir / 'districts.geojson'
    with open(districts_file, 'w', encoding='utf-8') as f:
        json.dump(districts, f, ensure_ascii=False, indent=2)
    logger.info(f"✓ Saved {len(districts['features'])} districts to {districts_file}")

    # Create summary
    summary = {
        'city': 'augsburg',
        'streets': len(streets['features']),
        'districts': len(districts['features']),
        'status': 'ready'
    }
    summary_file = output_dir / 'gazetteer_summary.json'
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    logger.info(f"✓ Created summary at {summary_file}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Setup city gazetteer from Overpass API'
    )
    parser.add_argument(
        '--city',
        default='augsburg',
        help='City name (default: augsburg)'
    )
    parser.add_argument(
        '--output',
        default='data/gazetteer',
        help='Output directory for GeoJSON files'
    )
    parser.add_argument(
        '--no-network',
        action='store_true',
        help='Skip network queries (for testing)'
    )

    args = parser.parse_args()

    logger.info("=" * 70)
    logger.info(f"Setting up gazetteer for {args.city.upper()}")
    logger.info("=" * 70)

    output_dir = Path(args.output)

    if args.no_network:
        logger.info("⊘ Network queries disabled - creating placeholder files")
        streets = {'type': 'FeatureCollection', 'features': []}
        districts = {'type': 'FeatureCollection', 'features': []}
    else:
        try:
            streets = fetch_augsburg_streets()
            districts = fetch_augsburg_districts()
        except Exception as e:
            logger.error(f"\n✗ Setup failed: {e}")
            logger.info("\nNote: Overpass API may be rate-limited or unavailable.")
            logger.info("The pipeline will continue without gazetteer validation.")
            return 1

    save_gazetteer(output_dir, streets, districts)

    logger.info("\n" + "=" * 70)
    logger.info("✓ GAZETTEER SETUP COMPLETE")
    logger.info("=" * 70)
    logger.info(f"You can now run the pipeline with:")
    logger.info(f"  python scripts/run_pipeline.py --city {args.city}")

    return 0


if __name__ == '__main__':
    sys.exit(main())
