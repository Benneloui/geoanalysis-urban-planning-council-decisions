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
import ssl
import certifi
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
        timeout: int = 10,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize spatial processor.

        Args:
            city: City name for geocoding context OR config dict
            cache_file: Path to geocoding cache JSON file
            rate_limit_sec: Minimum seconds between geocoding requests
            timeout: Geocoding request timeout
            config: Configuration dictionary
        """
        # Handle config dict as first argument (for tests)
        if isinstance(city, dict):
            config = city
            geocoding_config = config.get('geocoding', {})
            self.city = config.get('project', {}).get('city', 'augsburg').title()
            cache_file = geocoding_config.get('cache_file')
            self.rate_limit = geocoding_config.get('rate_limit', 1.0)
            self.timeout = geocoding_config.get('timeout', 10)
            user_agent = geocoding_config.get('user_agent', f"oparl-pipeline-{self.city}")
        else:
            self.city = city.title()
            self.rate_limit = rate_limit_sec
            self.timeout = timeout
            user_agent = f"oparl-pipeline-{self.city}"

        # Store config for later use
        self.config = config or {}
        geocoding_config = self.config.get('geocoding', {})

        self._last_request_time = 0

        # Initialize geocoder with user_agent and SSL settings
        self.user_agent = user_agent
        verify_ssl = geocoding_config.get('verify_ssl', True)

        # Create SSL context for Nominatim
        if verify_ssl:
            ssl_context = ssl.create_default_context(cafile=certifi.where())
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

        self.geocoder = Nominatim(
            user_agent=user_agent,
            timeout=self.timeout,
            ssl_context=ssl_context
        )

        # Load blocklist from config
        self.blocklist = set(
            w.lower() for w in self.config.get('location_extraction', {}).get('blocklist', [])
        )
        self.min_location_length = self.config.get('location_extraction', {}).get('min_length', 3)
        self.max_location_length = self.config.get('location_extraction', {}).get('max_length', 60)

        # Load gazetteer (streets, districts) for validation
        self.streets_gazetteer = self._load_gazetteer('streets')
        self.districts_gazetteer = self._load_gazetteer('districts')

        logger.info(f"Loaded {len(self.streets_gazetteer)} streets and {len(self.districts_gazetteer)} districts")

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

        # Load street list if available
        self.streets = self._load_street_list()

    def _load_street_list(self) -> List[str]:
        """Load known street names for the city."""
        street_file = Path("data") / f"{self.city}_streets.csv"
        if street_file.exists():
            try:
                import pandas as pd
                df = pd.read_csv(street_file)
                # Assume first column contains street names
                return df.iloc[:, 0].tolist()
            except Exception as e:
                logger.debug(f"Could not load street list: {e}")
        return []

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

    def _save_to_cache(self, key: str, value: Dict[str, Any]):
        """
        Save a single result to the cache.

        Args:
            key: Cache key
            value: Location data to cache
        """
        self.cache[key] = value

    def _load_gazetteer(self, gazetteer_type: str) -> set:
        """
        Load gazetteer data (streets or districts) from GeoJSON.

        Args:
            gazetteer_type: 'streets' or 'districts'

        Returns:
            Set of normalized location names
        """
        gazetteer_path = Path('data/gazetteer') / f'{gazetteer_type}.geojson'

        try:
            if not gazetteer_path.exists():
                logger.debug(f"Gazetteer not found: {gazetteer_path}")
                return set()

            with open(gazetteer_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            names = set()
            for feature in data.get('features', []):
                props = feature.get('properties', {})
                if 'name' in props:
                    names.add(props['name'].lower())

            logger.debug(f"Loaded {len(names)} {gazetteer_type} from gazetteer")
            return names
        except Exception as e:
            logger.debug(f"Could not load gazetteer {gazetteer_type}: {e}")
            return set()

    def _compile_patterns(self):
        """Compile regex patterns for spatial entity extraction."""
        # Gatekeeper pattern: Quick check to reject obvious non-locations before geocoding
        # Matches: Capitalized word(s) with optional numbers, umlauts, or address suffixes
        # Rejects: All-caps, too many words, mixed case, no capitals
        self.gatekeeper_pattern = re.compile(
            r"^[A-ZÄÖÜ](?:[a-zäöüß\-'/]|\s[A-ZÄÖÜ])*(?:\s+\d+[a-z]?)?$"
        )

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

        # Street name patterns (without number)
        self.street_pattern = re.compile(
            r'\b([A-ZÄÖÜ][a-zäöüß-]+(?:straße|str\.|platz|weg|allee|gasse))\b',
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

        # 1. Smart NER extraction with gazetteer coordinates (NO geocoding needed!)
        if self.location_extractor:
            try:
                # Use new method that returns coordinates from gazetteer
                if hasattr(self.location_extractor, 'get_locations_with_coordinates'):
                    smart_locations = self.location_extractor.get_locations_with_coordinates(text)
                    for loc in smart_locations:
                        locations.append({
                            'type': 'address',
                            'text': loc['name'],  # Use 'text' for consistency
                            'value': loc['name'],  # Keep 'value' for backward compatibility
                            'method': 'gazetteer',  # Mark as gazetteer-sourced
                            'latitude': loc['latitude'],
                            'longitude': loc['longitude'],
                            'source': 'gazetteer',
                            **base_fields
                        })
                else:
                    # Fallback to old method if new one not available
                    smart_locations = self.location_extractor.get_locations_from_text(text)
                    for loc in smart_locations:
                        locations.append({
                            'type': 'address',
                            'text': loc,  # Use 'text' for consistency
                            'value': loc,  # Keep 'value' for backward compatibility
                            'method': 'ner',
                            **base_fields
                        })
            except Exception as e:
                logger.debug(f"Smart extraction failed: {e}")

        # 2. B-Plan extraction
        for match in self.bplan_pattern.finditer(text):
            bplan_value = match.group(1).strip()
            locations.append({
                'type': 'bplan',
                'text': bplan_value,  # Use 'text' for consistency
                'value': bplan_value,  # Keep 'value' for backward compatibility
                'method': 'regex',
                'context': match.group(0),
                **base_fields
            })

        # 3. Flurnummer extraction
        for match in self.flur_pattern.finditer(text):
            flur_value = match.group(1).strip()
            locations.append({
                'type': 'flurnummer',
                'text': flur_value,  # Use 'text' for consistency
                'value': flur_value,  # Keep 'value' for backward compatibility
                'method': 'regex',
                'context': match.group(0),
                **base_fields
            })

        # 4. Address extraction
        for match in self.address_pattern.finditer(text):
            street = match.group(1).strip()
            number = match.group(2).strip()
            full_address = f"{street} {number}"
            locations.append({
                'type': 'address',
                'text': full_address,  # Use 'text' for consistency
                'value': full_address,  # Keep 'value' for backward compatibility
                'method': 'regex',
                **base_fields
            })

        # Extract streets already found in addresses to avoid duplicates
        found_streets = {loc['text'].split()[0].lower() for loc in locations if loc.get('type') == 'address'}

        # 4.5. Street name extraction (without house number)
        for match in self.street_pattern.finditer(text):
            street = match.group(1).strip()
            # Avoid duplicates with addresses
            if street.lower() not in found_streets:
                locations.append({
                    'type': 'street',
                    'text': street,  # Use 'text' for consistency
                    'value': street,  # Keep 'value' for backward compatibility
                    'method': 'regex',
                    **base_fields
                })

        # 5. District extraction (DISABLED: too many false positives without hardcoded district list)
        # To enable: create hardcoded list of Augsburg's 42 districts (e.g., "Oberhausen", "Göggingen")
        # and validate against it before adding to locations.
        # for match in self.district_pattern.finditer(text):
        #     district = match.group(1).strip()
        #     if len(district) > 3:  # Filter out too short matches
        #         locations.append({
        #             'type': 'district',
        #             'text': district,  # Use 'text' for consistency
        #             'value': district,  # Keep 'value' for backward compatibility
        #             'method': 'regex',
        #             **base_fields
        #         })

        # Deduplicate
        seen = set()
        unique_locations = []
        for loc in locations:
            key = (loc['type'], loc.get('text', loc.get('value', '')).lower())
            if key not in seen:
                seen.add(key)
                unique_locations.append(loc)

        # Sanity check: filter out blocklisted and invalid locations
        valid_locations = [loc for loc in unique_locations if self._is_valid_location(loc)]

        if len(valid_locations) < len(unique_locations):
            logger.debug(f"Filtered out {len(unique_locations) - len(valid_locations)} invalid locations")

        # Log if we extracted an unusual number of locations BEFORE gazetteer filtering
        if len(valid_locations) > 100:
            paper_info = f" for paper {paper_id}" if paper_id else ""
            logger.warning(f"⚠️  Extracted {len(valid_locations)} locations{paper_info} BEFORE gazetteer filter - potential extraction issue!")
            if pdf_url:
                logger.warning(f"   PDF URL: {pdf_url}")

        # GAZETTEER FIREWALL: Only keep locations that exist in our street gazetteer
        # This prevents wasting API calls on non-locations like "Arbeitsplatz", "Prozent", etc.
        gazetteer_filtered = []
        for loc in valid_locations:
            loc_text = loc.get('text', '').lower()

            # Skip very short texts that would match everything
            if len(loc_text) < 5:
                logger.debug(f"Filtered out too-short location: '{loc['text']}'")
                continue

            # Check if this location is in our gazetteer (exact match or very close)
            if loc_text in self.streets_gazetteer:
                gazetteer_filtered.append(loc)
            else:
                # Check for close matches (street must start with loc_text and be at most 10 chars longer)
                found_match = False
                for street in self.streets_gazetteer:
                    street_lower = street.lower()
                    # Allow match if location text is at least 60% of the street name
                    min_match_len = max(5, int(len(street_lower) * 0.6))
                    if len(loc_text) >= min_match_len and street_lower.startswith(loc_text):
                        gazetteer_filtered.append(loc)
                        found_match = True
                        break

                if not found_match:
                    logger.debug(f"Filtered out non-gazetteer location: '{loc['text']}'")

        if len(gazetteer_filtered) < len(valid_locations):
            logger.debug(f"Gazetteer filter: {len(valid_locations)} → {len(gazetteer_filtered)} locations")

        # Safety limit: cap at 50 locations per document to prevent runaway extraction
        MAX_LOCATIONS_PER_PAPER = 50
        if len(gazetteer_filtered) > MAX_LOCATIONS_PER_PAPER:
            paper_info = f" for paper {paper_id}" if paper_id else ""
            logger.warning(f"⚠️  Too many locations ({len(gazetteer_filtered)}){paper_info} - capping at {MAX_LOCATIONS_PER_PAPER}")
            if pdf_url:
                logger.warning(f"   PDF URL: {pdf_url}")
            # Keep only the first N unique location names
            seen_names = set()
            capped_locations = []
            for loc in gazetteer_filtered:
                name = loc.get('text', '').lower()
                if name not in seen_names:
                    seen_names.add(name)
                    capped_locations.append(loc)
                if len(capped_locations) >= MAX_LOCATIONS_PER_PAPER:
                    break
            gazetteer_filtered = capped_locations

        logger.debug(f"Extracted {len(gazetteer_filtered)} valid, gazetteer-verified locations from text")
        return gazetteer_filtered

    def _is_valid_location(self, location: Dict[str, Any]) -> bool:
        """
        Sanity check for extracted locations.

        Args:
            location: Location dict with 'text' field

        Returns:
            True if location passes validation checks
        """
        text = location.get('text', '').strip()

        # GATEKEEPER: Quick format check before expensive operations
        # Rejects obviously non-location text early (all-caps, lowercase start, weird chars)
        if not self.gatekeeper_pattern.match(text):
            return False

        # Check length bounds
        if len(text) < self.min_location_length:
            return False
        if len(text) > self.max_location_length:
            return False

        # Check blocklist (case-insensitive)
        if text.lower() in self.blocklist:
            return False

        # Check if first word is in blocklist (catches "Programm..." etc)
        first_word = text.split()[0].lower() if text.split() else ''
        if first_word in self.blocklist:
            return False

        # Reject purely numeric or single-character locations
        if text.replace(' ', '').isdigit() or len(text) == 1:
            return False

        # Reject locations with too many spaces (likely sentence fragments)
        space_count = text.count(' ')
        if space_count > 4 and location.get('type') not in ['bplan', 'flurnummer']:
            return False

        return True

    def _rate_limit(self):
        """Enforce rate limiting for geocoding requests."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self.rate_limit:
            time.sleep(self.rate_limit - elapsed)
        self._last_request_time = time.time()

    def _cache_key(self, query: str) -> str:
        """Generate cache key for a geocoding query."""
        return hashlib.md5(query.lower().encode()).hexdigest()

    def _geocode_location(self, location: Dict[str, Any], city: str = None) -> Optional[Dict[str, Any]]:
        """
        Geocode a single location dictionary from extract_locations.

        Args:
            location: Location dictionary with 'text' and 'type'
            city: City name for context

        Returns:
            Enriched location dict with coordinates or None
        """
        city_name = city or self.city
        location_text = location.get('text', location.get('value', ''))
        location_type = location.get('type', 'address')

        result = self.geocode(location_text, location_type)
        if result:
            # Add coordinates key for tests
            enriched = {**location, **result}
            if 'latitude' in result and 'longitude' in result:
                enriched['coordinates'] = {'lat': result['latitude'], 'lon': result['longitude']}
            return enriched
        return {**location, 'geocoded': False}

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
        gazetteer_count = 0
        geocoded_count = 0

        logger.info(f"Geocoding {len(locations)} locations")

        for i, loc in enumerate(locations):
            # Skip geocoding for locations that already have coordinates from gazetteer
            if loc.get('source') == 'gazetteer' and loc.get('latitude') and loc.get('longitude'):
                results.append(loc)
                gazetteer_count += 1
                continue

            # Use 'text' or fall back to 'value' for location name
            location_text = loc.get('text', loc.get('value', ''))
            result = self.geocode(location_text, loc.get('type', 'address'))

            if result:
                enriched = {**loc, **result}
                results.append(enriched)
                geocoded_count += 1
            else:
                results.append(loc)

            # Save cache periodically
            if (i + 1) % save_cache_interval == 0:
                self._save_cache()
                logger.info(f"Processed {i + 1}/{len(locations)} locations ({gazetteer_count} from gazetteer, {geocoded_count} geocoded)")

        # Final cache save
        self._save_cache()

        logger.info(f"Geocoding complete: {len(results)} results ({gazetteer_count} from gazetteer, {geocoded_count} geocoded)")
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
            papers: List of paper dictionaries with 'full_text' or 'pdf_text' field

        Returns:
            Papers enriched with 'locations' field
        """
        logger.info(f"Enriching {len(papers)} papers with spatial data")

        enriched = []

        for paper in papers:
            # Support both 'full_text' and 'pdf_text' keys
            text = paper.get('full_text') or paper.get('pdf_text', '')

            if not text:
                # Add empty locations list even if no text
                paper_copy = paper.copy()
                paper_copy['locations'] = []
                paper_copy['location_count'] = 0
                enriched.append(paper_copy)
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
