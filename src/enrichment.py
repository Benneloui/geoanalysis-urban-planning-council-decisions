"""
enrichment.py - Data Enrichment with External Sources

This module provides:
1. Wikidata entity linking for locations and topics
2. GeoNames hierarchical location data
3. Topic categorization using ML
4. Sentiment analysis for discussions (optional)
"""

from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
import logging
import time
import json
from urllib.parse import quote

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class EnrichedLocation:
    """Location enriched with external data"""
    original_text: str
    original_type: str
    wikidata_id: Optional[str] = None
    wikidata_label: Optional[str] = None
    wikidata_description: Optional[str] = None
    geonames_id: Optional[str] = None
    geonames_hierarchy: Optional[List[Dict[str, Any]]] = None
    alternative_names: List[str] = field(default_factory=list)
    population: Optional[int] = None
    elevation: Optional[float] = None
    wikipedia_url: Optional[str] = None


class WikidataEnricher:
    """
    Enrich locations and entities with Wikidata

    Queries Wikidata SPARQL endpoint to:
    - Link locations to Wikidata entities
    - Get additional metadata (population, elevation, etc.)
    - Find related entities
    """

    def __init__(self, user_agent: str = "GeomodelierungBot/1.0"):
        self.sparql_endpoint = "https://query.wikidata.org/sparql"
        self.user_agent = user_agent
        self.session = self._create_session()
        self.cache: Dict[str, Any] = {}

    def _create_session(self) -> requests.Session:
        """Create session with retry logic"""
        session = requests.Session()
        retry = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        session.headers.update({'User-Agent': self.user_agent})
        return session

    def search_entity(self, search_term: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Search for Wikidata entities

        Args:
            search_term: Text to search for
            limit: Maximum number of results

        Returns:
            List of matching entities with ID, label, description
        """
        # Check cache
        cache_key = f"search:{search_term}:{limit}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        api_url = "https://www.wikidata.org/w/api.php"

        params = {
            'action': 'wbsearchentities',
            'search': search_term,
            'language': 'de',
            'limit': limit,
            'format': 'json'
        }

        try:
            response = self.session.get(api_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            results = []
            for item in data.get('search', []):
                results.append({
                    'id': item.get('id'),
                    'label': item.get('label'),
                    'description': item.get('description', ''),
                    'url': item.get('concepturi')
                })

            # Cache results
            self.cache[cache_key] = results

            time.sleep(0.5)  # Rate limiting

            return results

        except Exception as e:
            logger.error(f"Wikidata search error for '{search_term}': {e}")
            return []

    def get_entity_details(self, entity_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a Wikidata entity

        Args:
            entity_id: Wikidata entity ID (e.g., 'Q2749')

        Returns:
            Dictionary with entity details
        """
        # Check cache
        cache_key = f"entity:{entity_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        sparql_query = f"""
        SELECT ?label ?description ?coord ?population ?elevation ?wikipedia WHERE {{
          wd:{entity_id} rdfs:label ?label .
          FILTER(LANG(?label) = "de")

          OPTIONAL {{ wd:{entity_id} schema:description ?description . FILTER(LANG(?description) = "de") }}
          OPTIONAL {{ wd:{entity_id} wdt:P625 ?coord . }}
          OPTIONAL {{ wd:{entity_id} wdt:P1082 ?population . }}
          OPTIONAL {{ wd:{entity_id} wdt:P2044 ?elevation . }}
          OPTIONAL {{
            ?wikipedia schema:about wd:{entity_id} .
            ?wikipedia schema:inLanguage "de" .
            FILTER(CONTAINS(str(?wikipedia), "wikipedia.org"))
          }}
        }}
        LIMIT 1
        """

        try:
            response = self.session.get(
                self.sparql_endpoint,
                params={'query': sparql_query, 'format': 'json'},
                timeout=15
            )
            response.raise_for_status()

            data = response.json()
            bindings = data['results']['bindings']

            if not bindings:
                return None

            result = bindings[0]

            details = {
                'id': entity_id,
                'label': result.get('label', {}).get('value'),
                'description': result.get('description', {}).get('value'),
                'coordinates': result.get('coord', {}).get('value'),
                'population': int(result['population']['value']) if 'population' in result else None,
                'elevation': float(result['elevation']['value']) if 'elevation' in result else None,
                'wikipedia_url': result.get('wikipedia', {}).get('value')
            }

            # Cache results
            self.cache[cache_key] = details

            time.sleep(0.5)  # Rate limiting

            return details

        except Exception as e:
            logger.error(f"Wikidata details error for {entity_id}: {e}")
            return None

    def link_location(self, location: Dict[str, Any], city: str = "Augsburg") -> EnrichedLocation:
        """
        Link location to Wikidata entity

        Args:
            location: Location dictionary with 'text' field
            city: City name for context

        Returns:
            EnrichedLocation object
        """
        text = location.get('text', '')
        location_type = location.get('type', '')

        # Search with city context for better results
        search_term = f"{text}, {city}"

        entities = self.search_entity(search_term, limit=3)

        enriched = EnrichedLocation(
            original_text=text,
            original_type=location_type
        )

        if entities:
            # Take best match
            best_match = entities[0]
            enriched.wikidata_id = best_match['id']
            enriched.wikidata_label = best_match['label']
            enriched.wikidata_description = best_match['description']

            # Get details
            details = self.get_entity_details(best_match['id'])
            if details:
                enriched.population = details.get('population')
                enriched.elevation = details.get('elevation')
                enriched.wikipedia_url = details.get('wikipedia_url')

        return enriched

    def batch_link_locations(
        self,
        locations: List[Dict[str, Any]],
        city: str = "Augsburg"
    ) -> List[EnrichedLocation]:
        """
        Link multiple locations in batch

        Args:
            locations: List of location dictionaries
            city: City name for context

        Returns:
            List of EnrichedLocation objects
        """
        enriched_locations = []

        for i, location in enumerate(locations):
            logger.info(f"Enriching location {i+1}/{len(locations)}: {location.get('text')}")

            enriched = self.link_location(location, city)
            enriched_locations.append(enriched)

            # Rate limiting
            if (i + 1) % 10 == 0:
                time.sleep(2)

        return enriched_locations


class GeoNamesEnricher:
    """
    Enrich locations with GeoNames hierarchical data

    Provides administrative hierarchy (country → state → district → city)
    """

    def __init__(self, username: str):
        """
        Initialize GeoNames enricher

        Args:
            username: GeoNames API username (free registration required)
        """
        self.username = username
        self.base_url = "http://api.geonames.org"
        self.session = requests.Session()

    def search_location(self, name: str, country: str = "DE") -> Optional[Dict[str, Any]]:
        """
        Search for location in GeoNames

        Args:
            name: Location name
            country: Country code (default: DE for Germany)

        Returns:
            Best matching GeoNames entry
        """
        params = {
            'q': name,
            'country': country,
            'maxRows': 5,
            'username': self.username,
            'type': 'json'
        }

        try:
            response = self.session.get(
                f"{self.base_url}/searchJSON",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            if data.get('geonames'):
                return data['geonames'][0]

            return None

        except Exception as e:
            logger.error(f"GeoNames search error for '{name}': {e}")
            return None

    def get_hierarchy(self, geoname_id: int) -> List[Dict[str, Any]]:
        """
        Get administrative hierarchy for location

        Args:
            geoname_id: GeoNames ID

        Returns:
            List of administrative levels from country to location
        """
        params = {
            'geonameId': geoname_id,
            'username': self.username,
            'type': 'json'
        }

        try:
            response = self.session.get(
                f"{self.base_url}/hierarchyJSON",
                params=params,
                timeout=10
            )
            response.raise_for_status()

            data = response.json()

            hierarchy = []
            for item in data.get('geonames', []):
                hierarchy.append({
                    'geonameId': item.get('geonameId'),
                    'name': item.get('name'),
                    'fcode': item.get('fcode'),
                    'fcodeName': item.get('fcodeName'),
                    'adminLevel': item.get('fcode')  # ADM1, ADM2, etc.
                })

            return hierarchy

        except Exception as e:
            logger.error(f"GeoNames hierarchy error for ID {geoname_id}: {e}")
            return []

    def enrich_location(self, location: Dict[str, Any]) -> Dict[str, Any]:
        """
        Enrich location with GeoNames data

        Args:
            location: Location dictionary

        Returns:
            Location with added GeoNames data
        """
        text = location.get('text', '')

        # Search for location
        geoname = self.search_location(text)

        if geoname:
            geoname_id = geoname.get('geonameId')

            location['geonames_id'] = geoname_id
            location['geonames_name'] = geoname.get('name')
            location['geonames_country'] = geoname.get('countryName')
            location['geonames_admin1'] = geoname.get('adminName1')  # State
            location['geonames_admin2'] = geoname.get('adminName2')  # District
            location['geonames_population'] = geoname.get('population')

            # Get hierarchy
            hierarchy = self.get_hierarchy(geoname_id)
            location['geonames_hierarchy'] = hierarchy

        return location


class TopicCategorizer:
    """
    Categorize documents by topic using ML

    Uses zero-shot classification or keyword-based matching
    """

    def __init__(self, categories: Optional[List[str]] = None):
        """
        Initialize topic categorizer

        Args:
            categories: List of topic categories
        """
        self.categories = categories or [
            'Verkehr',
            'Stadtentwicklung',
            'Bauprojekte',
            'Grünflächen',
            'Wohnungsbau',
            'Sanierung',
            'Bildung',
            'Soziales',
            'Kultur',
            'Wirtschaft'
        ]

        # Keywords for each category
        self.category_keywords = {
            'Verkehr': ['straße', 'verkehr', 'bus', 'rad', 'fahrrad', 'parkplatz', 'stau'],
            'Stadtentwicklung': ['entwicklung', 'planung', 'konzept', 'strategie', 'zukunft'],
            'Bauprojekte': ['bau', 'bebauung', 'neubau', 'bauvorhaben', 'baugebiet'],
            'Grünflächen': ['park', 'grün', 'baum', 'natur', 'garten', 'spielplatz'],
            'Wohnungsbau': ['wohnung', 'wohnen', 'wohngebiet', 'miete', 'sozialwohnungen'],
            'Sanierung': ['sanierung', 'renovierung', 'umbau', 'modernisierung'],
            'Bildung': ['schule', 'kita', 'kindergarten', 'bildung', 'lernen'],
            'Soziales': ['sozial', 'integration', 'migration', 'pflege', 'gesundheit'],
            'Kultur': ['kultur', 'museum', 'theater', 'veranstaltung', 'kunst'],
            'Wirtschaft': ['wirtschaft', 'gewerbe', 'unternehmen', 'arbeitsplätze', 'industrie']
        }

    def categorize_text(self, text: str, threshold: float = 0.3) -> List[Tuple[str, float]]:
        """
        Categorize text into topics

        Args:
            text: Text to categorize
            threshold: Minimum confidence threshold

        Returns:
            List of (category, confidence) tuples
        """
        text_lower = text.lower()

        scores = {}

        # Simple keyword-based scoring
        for category, keywords in self.category_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 1

            # Normalize by number of keywords
            normalized_score = score / len(keywords)

            if normalized_score >= threshold:
                scores[category] = normalized_score

        # Sort by score
        sorted_categories = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        return sorted_categories

    def categorize_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Categorize a paper document

        Args:
            paper: Paper dictionary with 'name' and optionally 'pdf_text'

        Returns:
            Paper with added 'categories' field
        """
        # Combine name and text for categorization
        text = paper.get('name', '')
        if 'pdf_text' in paper:
            text += " " + paper['pdf_text'][:1000]  # First 1000 chars

        categories = self.categorize_text(text)

        paper['categories'] = [
            {'category': cat, 'confidence': conf}
            for cat, conf in categories
        ]

        return paper


class SentimentAnalyzer:
    """
    Analyze sentiment of discussions and comments

    Uses German language sentiment models
    """

    def __init__(self):
        self.model_loaded = False
        try:
            # Try to load German sentiment model
            from transformers import pipeline
            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="oliverguhr/german-sentiment-bert"
            )
            self.model_loaded = True
        except ImportError:
            logger.warning("transformers library not installed - sentiment analysis disabled")
        except Exception as e:
            logger.warning(f"Could not load sentiment model: {e}")

    def analyze_text(self, text: str) -> Optional[Dict[str, Any]]:
        """
        Analyze sentiment of text

        Args:
            text: Text to analyze

        Returns:
            Dictionary with sentiment label and score
        """
        if not self.model_loaded:
            return None

        try:
            # Truncate to max model length
            text = text[:512]

            result = self.sentiment_pipeline(text)[0]

            return {
                'label': result['label'],
                'score': result['score']
            }

        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return None

    def analyze_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze sentiment of paper content

        Args:
            paper: Paper dictionary with text content

        Returns:
            Paper with added 'sentiment' field
        """
        text = paper.get('name', '')
        if 'pdf_text' in paper:
            text = paper['pdf_text'][:512]

        sentiment = self.analyze_text(text)

        if sentiment:
            paper['sentiment'] = sentiment

        return paper


# Example usage
if __name__ == '__main__':
    # Example: Enrich location with Wikidata
    enricher = WikidataEnricher()

    location = {
        'text': 'Maximilianstraße',
        'type': 'street'
    }

    enriched = enricher.link_location(location, city='Augsburg')

    print(f"Original: {enriched.original_text}")
    print(f"Wikidata ID: {enriched.wikidata_id}")
    print(f"Label: {enriched.wikidata_label}")
    print(f"Description: {enriched.wikidata_description}")
    print(f"Wikipedia: {enriched.wikipedia_url}")

    # Example: Categorize text
    categorizer = TopicCategorizer()

    text = """
    Beschluss über den Bebauungsplan für das Wohngebiet
    westlich der Maximilianstraße mit 200 neuen Wohnungen
    """

    categories = categorizer.categorize_text(text)
    print(f"\nCategories: {categories}")
