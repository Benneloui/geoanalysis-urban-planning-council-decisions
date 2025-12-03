"""
OParl API Client
================

Memory-efficient OParl API client with generator-based pagination,
exponential backoff, and robust error handling.

Usage:
    from src.client import OParlClient

    client = OParlClient(city="augsburg", config_path="config.yaml")

    # Stream papers without loading all into memory
    for paper in client.fetch_papers(start_date="2023-01-01"):
        print(paper['name'])

    # Fetch meetings
    for meeting in client.fetch_meetings(limit_pages=50):
        print(meeting['start'])
"""

import requests
import time
import logging
from typing import Generator, Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import yaml

logger = logging.getLogger(__name__)


class OParlClient:
    """
    OParl API Client with memory-efficient streaming and robust error handling.

    Attributes:
        city: City name (e.g., "augsburg")
        config: Configuration dictionary loaded from config.yaml
        session: Requests session with retry logic
        base_uri: Base URI for generating resource URIs
    """

    def __init__(
        self,
        city: str = "augsburg",
        config_path: Optional[str] = None,
        timeout: int = 40
    ):
        """
        Initialize OParl API Client.

        Args:
            city: City name matching config.yaml endpoints
            config_path: Path to config.yaml (optional, auto-detects if None)
            timeout: HTTP request timeout in seconds
        """
        self.city = city.lower()
        self.timeout = timeout
        self.config = self._load_config(config_path)
        self.session = self._create_session()
        self.base_uri = f"http://{self.city}.oparl-analytics.org/"

        # Extract OParl settings from config
        oparl_config = self.config.get('oparl', {})
        self.system_url = self._normalize_url(
            oparl_config.get('endpoints', {}).get(self.city)
        )
        self.start_date = oparl_config.get('start_date', '2023-01-01T00:00:00Z')
        self.end_date = oparl_config.get('end_date', '2025-12-31T23:59:59Z')
        self.max_pages_meetings = oparl_config.get('max_pages_meetings', 50)
        self.retry_attempts = oparl_config.get('retry_attempts', 5)
        self.retry_pause = oparl_config.get('retry_pause_sec', 2)

        # Cache for body and system data
        self._body_cache: Optional[Dict[str, Any]] = None
        self._system_cache: Optional[Dict[str, Any]] = None

        logger.info(f"OParlClient initialized for {city} - System: {self.system_url}")

    def _load_config(self, config_path: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration from config.yaml."""
        if config_path is None:
            # Auto-detect config.yaml in project root
            current_dir = Path(__file__).resolve().parent
            config_path = current_dir.parent / "config.yaml"

        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Config file not found: {config_file}")

        with open(config_file, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _normalize_url(self, url: Optional[str]) -> str:
        """Ensure URL has https:// prefix."""
        if not url:
            raise ValueError(f"No OParl endpoint configured for city: {self.city}")

        if not url.startswith(('http://', 'https://')):
            url = f"https://{url}"

        return url

    def _create_session(self) -> requests.Session:
        """
        Create requests session with exponential backoff retry strategy.

        Returns:
            Configured requests.Session
        """
        session = requests.Session()

        retry_strategy = Retry(
            total=self.config.get('oparl', {}).get('retry_attempts', 5),
            backoff_factor=self.config.get('oparl', {}).get('retry_pause_sec', 2),
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )

        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=10,
            pool_maxsize=10
        )

        session.mount("https://", adapter)
        session.mount("http://", adapter)

        # Set user agent
        session.headers.update({
            'User-Agent': f'OParl-Pipeline/{self.config.get("project", {}).get("version", "0.1")}'
        })

        return session

    def _get_json(self, url: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Fetch JSON from URL with error handling.

        Args:
            url: API endpoint URL
            params: Query parameters

        Returns:
            Parsed JSON response

        Raises:
            requests.exceptions.RequestException: On network/HTTP errors
        """
        try:
            response = self.session.get(url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

    def get_system(self) -> Dict[str, Any]:
        """
        Get OParl system object.

        Returns:
            System metadata dictionary
        """
        if self._system_cache:
            return self._system_cache

        logger.info(f"Fetching system from {self.system_url}")
        self._system_cache = self._get_json(self.system_url)
        return self._system_cache

    def get_body(self) -> Dict[str, Any]:
        """
        Get the first body object for the city.

        Returns:
            Body object with all endpoints
        """
        if self._body_cache:
            return self._body_cache

        system = self.get_system()

        # Get bodies list URL
        bodies_url = system.get('body')
        if isinstance(bodies_url, list):
            bodies_url = bodies_url[0] if bodies_url else None

        if not bodies_url:
            raise ValueError("No body URL found in system object")

        logger.info(f"Fetching body list from {bodies_url}")
        bodies_data = self._get_json(bodies_url)

        # Get first body
        bodies_list = bodies_data.get('data', [])
        if not bodies_list:
            raise ValueError("No bodies found in bodies list")

        body_id = bodies_list[0].get('id')
        logger.info(f"Fetching body details: {bodies_list[0].get('name', 'Unknown')}")

        self._body_cache = self._get_json(body_id)
        return self._body_cache

    def _paginate(
        self,
        start_url: str,
        limit_pages: Optional[int] = None,
        params: Optional[Dict] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Generator for paginated API endpoints.

        Args:
            start_url: Initial endpoint URL
            limit_pages: Maximum pages to fetch (None = unlimited)
            params: Additional query parameters

        Yields:
            Individual items from paginated results
        """
        url = start_url
        page_count = 0

        while url:
            if limit_pages and page_count >= limit_pages:
                logger.info(f"Reached page limit: {limit_pages}")
                break

            try:
                data = self._get_json(url, params=params)
                items = data.get('data', [])

                # Yield individual items
                for item in items:
                    yield item

                # Get next page URL
                url = data.get('links', {}).get('next')
                page_count += 1

                if page_count % 10 == 0:
                    logger.info(f"Processed {page_count} pages...")

                # Be nice to the API
                time.sleep(0.2)

            except requests.exceptions.RequestException as e:
                logger.error(f"Error during pagination at page {page_count}: {e}")
                break

    def fetch_papers(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit_pages: Optional[int] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream papers from OParl API.

        Args:
            start_date: ISO 8601 datetime (e.g., "2023-01-01T00:00:00Z")
            end_date: ISO 8601 datetime
            limit_pages: Maximum pages to fetch

        Yields:
            Paper objects

        Example:
            for paper in client.fetch_papers(start_date="2023-01-01"):
                if paper.get('mainFile'):
                    print(f"Paper: {paper['name']}")
        """
        body = self.get_body()
        papers_url = body.get('paper')

        if not papers_url:
            raise ValueError("No papers endpoint found in body")

        params = {}
        if start_date or self.start_date:
            params['modified_since'] = start_date or self.start_date

        logger.info(f"Fetching papers from {papers_url}")
        logger.info(f"Date filter: {params.get('modified_since', 'none')}")

        yield from self._paginate(papers_url, limit_pages, params)

    def fetch_meetings(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit_pages: Optional[int] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream meetings from OParl API.

        Args:
            start_date: ISO 8601 datetime
            end_date: ISO 8601 datetime
            limit_pages: Maximum pages to fetch (defaults to config)

        Yields:
            Meeting objects
        """
        body = self.get_body()
        meetings_url = body.get('meeting')

        if not meetings_url:
            raise ValueError("No meetings endpoint found in body")

        if limit_pages is None:
            limit_pages = self.max_pages_meetings

        params = {}
        if start_date or self.start_date:
            params['modified_since'] = start_date or self.start_date

        logger.info(f"Fetching meetings from {meetings_url}")
        logger.info(f"Date filter: {params.get('modified_since', 'none')}")
        logger.info(f"Page limit: {limit_pages}")

        yield from self._paginate(meetings_url, limit_pages, params)

    def fetch_agenda_items(
        self,
        meeting_id: str
    ) -> List[Dict[str, Any]]:
        """
        Fetch agenda items for a specific meeting.

        Args:
            meeting_id: Meeting URL/ID

        Returns:
            List of agenda item objects
        """
        try:
            meeting = self._get_json(meeting_id)
            agenda_items = meeting.get('agendaItem', [])

            # If agenda items are URLs, fetch them
            if agenda_items and isinstance(agenda_items[0], str):
                items = []
                for item_url in agenda_items:
                    items.append(self._get_json(item_url))
                return items

            return agenda_items
        except Exception as e:
            logger.warning(f"Could not fetch agenda items for {meeting_id}: {e}")
            return []

    def fetch_organizations(
        self,
        limit_pages: Optional[int] = None
    ) -> Generator[Dict[str, Any], None, None]:
        """
        Stream organizations from OParl API.

        Args:
            limit_pages: Maximum pages to fetch

        Yields:
            Organization objects
        """
        body = self.get_body()
        orgs_url = body.get('organization')

        if not orgs_url:
            raise ValueError("No organizations endpoint found in body")

        logger.info(f"Fetching organizations from {orgs_url}")
        yield from self._paginate(orgs_url, limit_pages)

    def get_organization_name(self, org_url: str) -> str:
        """
        Get organization name from URL.

        Args:
            org_url: Organization URL

        Returns:
            Organization name or URL if fetch fails
        """
        if not org_url or org_url == 'Unknown':
            return 'Unbekannt'

        try:
            org = self._get_json(org_url)
            return org.get('name', org_url)
        except Exception as e:
            logger.warning(f"Could not fetch organization {org_url}: {e}")
            return org_url

    def generate_uri(self, resource_type: str, original_id: str) -> str:
        """
        Generate standardized URI for a resource.

        Args:
            resource_type: Type of resource (e.g., "meeting", "paper")
            original_id: Original OParl ID/URL

        Returns:
            Standardized URI string

        Example:
            >>> client.generate_uri("paper", "https://api.example.org/paper/123")
            "http://augsburg.oparl-analytics.org/paper/123"
        """
        # Extract ID from URL if needed
        if original_id.startswith('http'):
            resource_id = original_id.split('/')[-1]
        else:
            resource_id = original_id

        return f"{self.base_uri}{resource_type}/{resource_id}"

    def close(self):
        """Close the session and clean up resources."""
        self.session.close()
        logger.info("OParlClient session closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Convenience function for backward compatibility
def get_robust_session() -> requests.Session:
    """
    Create a robust session with retry logic (legacy function).

    Returns:
        Configured requests.Session
    """
    session = requests.Session()
    retry_strategy = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
