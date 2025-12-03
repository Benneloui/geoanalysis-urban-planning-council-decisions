"""
Spatial Data Processing
=======================

Extract locations from text and geocode them using hierarchical strategy.
Integrates NER, regex patterns, and geocoding services with caching.

Usage:
    from src.spatial import SpatialProcessor

    processor = SpatialProcessor()

    # Extract locations from text
    locations = processor.extract_locations(text)

    # Geocode locations
    results = processor.geocode_batch(locations)

    # Generate WKT for RDF
    wkt = processor.to_wkt(lat, lon)
"""

import logging
import time
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import pandas as pd
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import hashlib

logger = logging.getLogger(__name__)

# Try to import location extractor
try:
    from .location_extractor import AugsburgLocationExtractor
    HAS_LOCATION_EXTRACTOR = True
except ImportError:
    HAS_LOCATION_EXTRACTOR = False
    logger.warning("location_extractor not available")


class SpatialProcessor:
    """
    Extract and geocode spatial entities from text.

    Extraction methods:
    1. Smart NER (using location_extractor)
    2. Regex patterns (B-Pläne, Flurnummern, addresses)

    Geocoding strategy:
    1. Check cache
    2. Try full address
    3. Fallback to district/city level

    Attributes:
        geocoder: Nominatim geocoder instance
        cache: Geocoding cache dictionary
        location_extractor: Smart location extractor (if available)
    """

    def __init__(
        self,
        city: str = "augsburg",
        cache_file: Optional[str] = None,
        rate_limit_sec: float = 1.0,
        timeout: int = 10
    ):
        """
        Initialize spatial processor.

        Args:
            city: City name for geocoding context
            cache_file: Path to geocoding cache JSON file
            rate_limit_sec: Minimum seconds between geocoding requests
            timeout: Geocoding request timeout
        """
        self.city = city.title()
        self.rate_limit = rate_limit_sec
        self.timeout = timeout
        self._last_request_time = 0

        # Initialize geocoder
        self.geocoder = Nominatim(
            user_agent=f"oparl-pipeline-{city}",
            timeout=timeout
        )

        # Setup cache
        if cache_file is None:
            cache_file = f"data/processed/geocoding_cache_{city}.json"

        self.cache_file = Path(cache_file)
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.cache = self._load_cache()

        # Initialize location extractor if available
        if HAS_LOCATION_EXTRACTOR:
            try:
                self.location_extractor = AugsburgLocationExtractor()
                logger.info("Smart location extractor initialized")
            except Exception as e:
                logger.warning(f"Could not initialize location extractor: {e}")
                self.location_extractor = None
        else:
            self.location_extractor = None

        # Compile regex patterns
        self._compile_patterns()

        logger.info(f"SpatialProcessor initialized for {self.city}")
        logger.info(f"Cache: {len(self.cache)} entries")

    def _load_cache(self) -> Dict[str, Any]:
        """Load geocoding cache from JSON file."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
                logger.info(f"Loaded {len(cache)} cached geocoding results")
                return cache
            except Exception as e:
                logger.warning(f"Could not load cache: {e}")

        return {}

    def _save_cache(self):
        """Save geocoding cache to JSON file."""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.cache, f, ensure_ascii=False, indent=2)
            logger.debug(f"Saved {len(self.cache)} entries to cache")
        except Exception as e:
            logger.warning(f"Could not save cache: {e}")

    def _compile_patterns(self):
        """Compile regex patterns for spatial entity extraction."""
        # Bebauungsplan (B-Plan) patterns
        self.bplan_pattern = re.compile(
            r'Bebauungsplan(?:\s+(?:Nr\.?|Nummer))?\s*([A-Z]?\d+[a-z]?(?:\s*[-/]\s*\d+)?)',
            re.IGNORECASE
        )

        # Flurnummer patterns
        self.flur_pattern = re.compile(
            r'Flur(?:stück)?(?:\s+(?:Nr\.?|Nummer))?\s*(\d+(?:\s*/\s*\d+)?)',
            re.IGNORECASE
        )

        # German address patterns (street + number)
        self.address_pattern = re.compile(
            r'([A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|platz|weg|allee|gasse))\s+(\d+[a-z]?)',
            re.IGNORECASE
        )

        # District/area patterns
        self.district_pattern = re.compile(
            r'(?:Stadtteil|Stadtbezirk|in)\s+([A-ZÄÖÜ][a-zäöüß\s]+)',
            re.IGNORECASE
        )

    def extract_locations(
        self,
        text: str,
        paper_id: Optional[str] = None,
        pdf_url: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Extract all location mentions from text.

        Args:
            text: Input text
            paper_id: Paper ID for tracking source (optional)
            pdf_url: PDF URL for linking back to document (optional)

        Returns:
            List of location dictionaries with type, value, and source info

        Example:
            [
                {
                    "type": "address",
                    "value": "Maximilianstraße 1",
                    "paper_id": "123",
                    "pdf_url": "https://..."
                },
                {"type": "bplan", "value": "45", "paper_id": "123"},
                {"type": "district", "value": "Oberhausen", "paper_id": "123"}
            ]
        """
        if not text:
            return []


        locations = []

        # Base fields for all locations
        base_fields = {}
        if paper_id:
            base_fields['paper_id'] = paper_id
        if pdf_url:
            base_fields['pdf_url'] = pdf_url

        # 1. Smart NER extraction
        if self.location_extractor:
            try:
                smart_locations = self.location_extractor.get_locations_from_text(text)
                for loc in smart_locations:
                    locations.append({
                        'type': 'address',
                        'value': loc,
                        'method': 'ner',
                        **base_fields
                    })
            except Exception as e:
                logger.debug(f"Smart extraction failed: {e}")

        # 2. B-Plan extraction
        for match in self.bplan_pattern.finditer(text):
            locations.append({
                'type': 'bplan',
                'value': match.group(1).strip(),
                'method': 'regex',
                'context': match.group(0),
                **base_fields
            })

        # 3. Flurnummer extraction
        for match in self.flur_pattern.finditer(text):
            locations.append({
                'type': 'flurnummer',
                'value': match.group(1).strip(),
                'method': 'regex',
                'context': match.group(0),
                **base_fields
            })

        # 4. Address extraction
        for match in self.address_pattern.finditer(text):
            street = match.group(1).strip()
            number = match.group(2).strip()
            locations.append({
                'type': 'address',
                'value': f"{street} {number}",
                'method': 'regex',
                **base_fields
            })

        # 5. District extraction
        for match in self.district_pattern.finditer(text):
            district = match.group(1).strip()
            if len(district) > 3:  # Filter out too short matches
                locations.append({
                    'type': 'district',
                    'value': district,
                    'method': 'regex',
                    **base_fields
                })        # Deduplicate
        seen = set()
        unique_locations = []
        for loc in locations:
            key = (loc['type'], loc['value'].lower())
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)

        logger.debug(f"Extracted {len(unique_locations)} locations from text")
        return unique_locations

    def _rate_limit(self):
        """Enforce rate limiting for geocoding requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _cache_key(self, query: str) -> str:
        """Generate cache key for a geocoding query."""
        return hashlib.md5(query.lower().encode()).hexdigest()

    def geocode(
        self,
        location: str,
        location_type: str = "address"
    ) -> Optional[Dict[str, Any]]:
        """
        Geocode a single location with hierarchical fallback.

        Args:
            location: Location string
            location_type: Type of location (address, district, bplan, etc.)

        Returns:
            Geocoding result dictionary or None

        Result format:
            {
                "query": "Maximilianstraße 1, Augsburg",
                "latitude": 48.369...,
                "longitude": 10.898...,
                "display_name": "...",
                "type": "house",
                "importance": 0.5
            }
        """
        # Check cache
        cache_key = self._cache_key(location)
        if cache_key in self.cache:
            logger.debug(f"Cache hit: {location}")
            return self.cache[cache_key]

        # Don't geocode technical IDs (B-Pläne, Flurnummern)
        if location_type in ['bplan', 'flurnummer']:
            logger.debug(f"Skipping geocoding for {location_type}: {location}")
            return None

        # Hierarchical geocoding strategy
        queries = []

        if location_type == "address":
            # Try full address with city
            queries.append(f"{location}, {self.city}, Deutschland")
            # Try just city (fallback)
            queries.append(f"{self.city}, Deutschland")
        elif location_type == "district":
            # Try district with city
            queries.append(f"{location}, {self.city}, Deutschland")
            # Try just city (fallback)
            queries.append(f"{self.city}, Deutschland")
        else:
            # Generic location
            queries.append(f"{location}, {self.city}, Deutschland")

        # Try each query
        for query in queries:
            self._rate_limit()

            try:
                logger.debug(f"Geocoding: {query}")
                result = self.geocoder.geocode(query, exactly_one=True)

                if result:
                    geocoded = {
                        'query': query,
                        'latitude': result.latitude,
                        'longitude': result.longitude,
                        'display_name': result.address,
                        'type': result.raw.get('type'),
                        'importance': result.raw.get('importance'),
                        'cached': False
                    }

                    # Cache result
                    self.cache[cache_key] = geocoded

                    logger.debug(f"Geocoded: {location} -> ({result.latitude}, {result.longitude})")
                    return geocoded

            except (GeocoderTimedOut, GeocoderServiceError) as e:
                logger.warning(f"Geocoding error for '{query}': {e}")
                continue
            except Exception as e:
                logger.error(f"Unexpected geocoding error: {e}")
                continue

        # All attempts failed
        logger.debug(f"Geocoding failed for: {location}")
        return None

    def geocode_batch(
        self,
        locations: List[Dict[str, Any]],
        save_cache_interval: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Geocode multiple locations with caching and rate limiting.

        Args:
            locations: List of location dictionaries from extract_locations
            save_cache_interval: Save cache every N requests

        Returns:
            List of enriched location dictionaries with coordinates
        """
        results = []

        logger.info(f"Geocoding {len(locations)} locations")

        for i, loc in enumerate(locations):
            result = self.geocode(loc['value'], loc['type'])

            if result:
                enriched = {**loc, **result}
                results.append(enriched)
            else:
                results.append(loc)

            # Save cache periodically
            if (i + 1) % save_cache_interval == 0:
                self._save_cache()
                logger.info(f"Geocoded {i + 1}/{len(locations)} locations")

        # Final cache save
        self._save_cache()

        logger.info(f"Geocoding complete: {len(results)} results")
        return results

    def to_wkt(
        self,
        latitude: float,
        longitude: float,
        srid: int = 4326
    ) -> str:
        """
        Convert coordinates to WKT (Well-Known Text) for GeoSPARQL.

        Args:
            latitude: Latitude
            longitude: Longitude
            srid: Spatial reference system ID (4326 = WGS84)

        Returns:
            WKT string

        Example:
            >>> processor.to_wkt(48.369, 10.898)
            "<http://www.opengis.net/def/crs/EPSG/0/4326> POINT(10.898 48.369)"
        """
        return f"<http://www.opengis.net/def/crs/EPSG/0/{srid}> POINT({longitude} {latitude})"

    def enrich_papers_with_locations(
        self,
        papers: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Extract and geocode locations from papers.

        Args:
            papers: List of paper dictionaries with 'full_text' field

        Returns:
            Papers enriched with 'locations' field
        """
        logger.info(f"Enriching {len(papers)} papers with spatial data")

        enriched = []

        for paper in papers:
            text = paper.get('full_text', '')

            if not text:
                enriched.append(paper)
                continue

            # Extract locations with paper_id and pdf_url tracking
            locations = self.extract_locations(
                text,
                paper_id=paper.get('id'),
                pdf_url=paper.get('pdf_url')
            )

            # Geocode
            geocoded = self.geocode_batch(locations)

            # Add to paper
            paper_copy = paper.copy()
            paper_copy['locations'] = geocoded
            paper_copy['location_count'] = len(geocoded)

            enriched.append(paper_copy)

        logger.info("Spatial enrichment complete")
        return enriched

    def close(self):
        """Save cache and clean up resources."""
        self._save_cache()
        logger.info("SpatialProcessor closed")


# Standalone helper functions
def extract_bplans(text: str) -> List[str]:
    """
    Extract Bebauungsplan numbers from text.

    Args:
        text: Input text

    Returns:
        List of B-Plan numbers
    """
    pattern = re.compile(
        r'Bebauungsplan(?:\s+(?:Nr\.?|Nummer))?\s*([A-Z]?\d+[a-z]?(?:\s*[-/]\s*\d+)?)',
        re.IGNORECASE
    )
    return [m.group(1).strip() for m in pattern.finditer(text)]


def extract_flurnummern(text: str) -> List[str]:
    """
    Extract Flurnummern from text.

    Args:
        text: Input text

    Returns:
        List of Flurnummern
    """
    pattern = re.compile(
        r'Flur(?:stück)?(?:\s+(?:Nr\.?|Nummer))?\s*(\d+(?:\s*/\s*\d+)?)',
        re.IGNORECASE
    )
    return [m.group(1).strip() for m in pattern.finditer(text)]
