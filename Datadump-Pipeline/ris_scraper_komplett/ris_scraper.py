"""
Web Scraper für Ratsinformationssysteme (RIS)
==============================================

Unterstützt verschiedene RIS-Systeme:
- ALLRIS (CC e-gov)
- SessionNet (STERNBERG)
- eSitzungsdienst
- sd.net RIM

Features:
- Automatische Erkennung des RIS-Typs
- Rate Limiting
- Session-Handling
- Fehlertoleranz
- Fortschritts-Speicherung
- HTML-Dump-Export

Abhängigkeiten:
    pip install requests beautifulsoup4 lxml selenium tqdm pyyaml
"""

import os
import re
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse, parse_qs
from dataclasses import dataclass, asdict
import hashlib

# HTTP & Parsing
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# Progress & Utils
from tqdm import tqdm
import yaml

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== DATA MODELS ====================

@dataclass
class ScrapedMeeting:
    """Strukturierte Daten einer Sitzung"""
    url: str
    title: str
    date: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    organization: Optional[str] = None
    status: Optional[str] = None
    html_content: Optional[str] = None
    agenda_items: List[Dict] = None
    documents: List[Dict] = None
    scraped_at: str = None
    
    def __post_init__(self):
        if self.scraped_at is None:
            self.scraped_at = datetime.now().isoformat()
        if self.agenda_items is None:
            self.agenda_items = []
        if self.documents is None:
            self.documents = []


@dataclass
class ScraperConfig:
    """Konfiguration für den Scraper"""
    base_url: str
    output_dir: str = "./scraped_data"
    max_pages: int = 50
    rate_limit_seconds: float = 1.0
    timeout_seconds: int = 30
    retry_attempts: int = 3
    user_agent: str = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    
    # Datumsfilter
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None
    
    # RIS-System (auto-detect oder manuell)
    ris_type: Optional[str] = None  # 'allris', 'sessionnet', 'esitzungsdienst'


# ==================== HTTP CLIENT ====================

class RobustHTTPClient:
    """HTTP Client mit Retry-Logic und Rate Limiting"""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.session = requests.Session()
        
        # Retry Strategy
        retry_strategy = Retry(
            total=config.retry_attempts,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        # Headers
        self.session.headers.update({
            'User-Agent': config.user_agent,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'de-DE,de;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
        # Rate limiting
        self.last_request_time = 0
    
    def get(self, url: str, **kwargs) -> requests.Response:
        """GET-Request mit Rate Limiting"""
        
        # Rate limiting
        elapsed = time.time() - self.last_request_time
        if elapsed < self.config.rate_limit_seconds:
            time.sleep(self.config.rate_limit_seconds - elapsed)
        
        # Request
        try:
            kwargs.setdefault('timeout', self.config.timeout_seconds)
            response = self.session.get(url, **kwargs)
            response.raise_for_status()
            
            self.last_request_time = time.time()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            raise
    
    def post(self, url: str, **kwargs) -> requests.Response:
        """POST-Request mit Rate Limiting"""
        
        elapsed = time.time() - self.last_request_time
        if elapsed < self.config.rate_limit_seconds:
            time.sleep(self.config.rate_limit_seconds - elapsed)
        
        try:
            kwargs.setdefault('timeout', self.config.timeout_seconds)
            response = self.session.post(url, **kwargs)
            response.raise_for_status()
            
            self.last_request_time = time.time()
            return response
            
        except requests.exceptions.RequestException as e:
            logger.error(f"POST failed for {url}: {e}")
            raise


# ==================== RIS TYPE DETECTION ====================

class RISTypeDetector:
    """Erkennt automatisch den Typ des Ratsinformationssystems"""
    
    SIGNATURES = {
        'allris': [
            'ALLRIS',
            'CC e-gov',
            'ai-info.asp',
            'si-info.asp',
            'to-info.asp'
        ],
        'sessionnet': [
            'SessionNet',
            'STERNBERG',
            'sessionnetbi',
            'getfile.php',
            'meetingdetail.php'
        ],
        'esitzungsdienst': [
            'eSitzungsdienst',
            'infosystem',
            'sitzung.php',
            'vorlage.php'
        ],
        'sdnet': [
            'sd.net',
            'RIM',
            'sdnetrim'
        ]
    }
    
    @classmethod
    def detect(cls, html: str, url: str) -> str:
        """Erkennt RIS-Typ aus HTML und URL"""
        
        html_lower = html.lower()
        url_lower = url.lower()
        
        for ris_type, signatures in cls.SIGNATURES.items():
            for signature in signatures:
                if signature.lower() in html_lower or signature.lower() in url_lower:
                    logger.info(f"Detected RIS type: {ris_type}")
                    return ris_type
        
        logger.warning("Could not detect RIS type - using generic scraper")
        return 'generic'


# ==================== SCRAPER IMPLEMENTATIONS ====================

class BaseRISScraper:
    """Basis-Klasse für RIS-Scraper"""
    
    def __init__(self, config: ScraperConfig):
        self.config = config
        self.client = RobustHTTPClient(config)
        self.scraped_urls: Set[str] = set()
        
        # Output-Verzeichnis erstellen
        self.output_dir = Path(config.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Fortschritt laden
        self.progress_file = self.output_dir / "scraping_progress.json"
        self.load_progress()
    
    def load_progress(self):
        """Lädt gespeicherten Fortschritt"""
        if self.progress_file.exists():
            with open(self.progress_file, 'r') as f:
                data = json.load(f)
                self.scraped_urls = set(data.get('scraped_urls', []))
                logger.info(f"Loaded progress: {len(self.scraped_urls)} URLs already scraped")
    
    def save_progress(self):
        """Speichert Fortschritt"""
        with open(self.progress_file, 'w') as f:
            json.dump({
                'scraped_urls': list(self.scraped_urls),
                'last_update': datetime.now().isoformat()
            }, f, indent=2)
    
    def save_html(self, url: str, html: str, meeting_id: str = None):
        """Speichert HTML-Datei"""
        
        if meeting_id is None:
            # Generiere Meeting-ID aus URL
            meeting_id = hashlib.md5(url.encode()).hexdigest()[:12]
        
        # Sanitize filename
        filename = f"meeting_{meeting_id}.html"
        filepath = self.output_dir / "html" / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.debug(f"Saved HTML: {filepath}")
        return str(filepath)
    
    def save_meeting_json(self, meeting: ScrapedMeeting):
        """Speichert Meeting als JSON"""
        
        meeting_id = hashlib.md5(meeting.url.encode()).hexdigest()[:12]
        filename = f"meeting_{meeting_id}.json"
        filepath = self.output_dir / "json" / filename
        filepath.parent.mkdir(exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(asdict(meeting), f, indent=2, ensure_ascii=False)
        
        logger.debug(f"Saved JSON: {filepath}")
    
    def scrape(self) -> List[ScrapedMeeting]:
        """Hauptmethode - überschreiben in Subklassen"""
        raise NotImplementedError


class ALLRISScraper(BaseRISScraper):
    """Scraper für ALLRIS (CC e-gov) Systeme"""
    
    def find_meeting_links(self) -> List[str]:
        """Findet alle Meeting-Links"""
        
        logger.info("Searching for meeting links in ALLRIS...")
        
        # Typische ALLRIS Startseiten
        search_urls = [
            f"{self.config.base_url}/si-info.asp",
            f"{self.config.base_url}/si0040.asp",
            f"{self.config.base_url}/si020.asp",
        ]
        
        meeting_links = []
        
        for search_url in search_urls:
            try:
                response = self.client.get(search_url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Finde alle Links zu Sitzungen (si-info.asp)
                for link in soup.find_all('a', href=re.compile(r'si-info\.asp')):
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.config.base_url, href)
                        if full_url not in self.scraped_urls:
                            meeting_links.append(full_url)
                
                logger.info(f"Found {len(meeting_links)} meeting links from {search_url}")
                
            except Exception as e:
                logger.error(f"Error searching {search_url}: {e}")
                continue
        
        return list(set(meeting_links))[:self.config.max_pages]
    
    def scrape_meeting(self, url: str) -> Optional[ScrapedMeeting]:
        """Scrapt eine einzelne Sitzung"""
        
        try:
            response = self.client.get(url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Titel
            title = None
            h1 = soup.find('h1')
            if h1:
                title = h1.get_text(strip=True)
            
            # Datum & Zeit
            date = None
            time_str = None
            
            # Suche nach typischen ALLRIS-Tabellen
            for td in soup.find_all('td', class_=re.compile(r'text', re.I)):
                text = td.get_text(strip=True)
                
                # Datumspattern
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', text)
                if date_match:
                    date = date_match.group(1)
                
                # Zeitpattern
                time_match = re.search(r'(\d{1,2}:\d{2})', text)
                if time_match:
                    time_str = time_match.group(1)
            
            # Ort
            location = None
            for td in soup.find_all('td'):
                text = td.get_text(strip=True)
                if 'Ort' in text or 'Raum' in text:
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        location = next_td.get_text(strip=True)
            
            # Gremium
            organization = None
            for td in soup.find_all('td'):
                text = td.get_text(strip=True)
                if 'Gremium' in text:
                    next_td = td.find_next_sibling('td')
                    if next_td:
                        organization = next_td.get_text(strip=True)
            
            # Tagesordnung
            agenda_items = []
            # Suche nach TO-Tabelle
            for table in soup.find_all('table'):
                # ALLRIS hat oft class="risdeco"
                rows = table.find_all('tr')
                for idx, row in enumerate(rows[1:], 1):  # Skip header
                    cells = row.find_all('td')
                    if len(cells) >= 2:
                        number = cells[0].get_text(strip=True)
                        title_td = cells[1]
                        
                        agenda_items.append({
                            'number': number,
                            'title': title_td.get_text(strip=True),
                            'position': idx
                        })
            
            # Dokumente
            documents = []
            for link in soup.find_all('a', href=re.compile(r'\.pdf|do-info\.asp')):
                doc_url = urljoin(url, link.get('href'))
                documents.append({
                    'title': link.get_text(strip=True),
                    'url': doc_url
                })
            
            # HTML speichern
            html_path = self.save_html(url, response.text)
            
            meeting = ScrapedMeeting(
                url=url,
                title=title or "Unbekannte Sitzung",
                date=date,
                time=time_str,
                location=location,
                organization=organization,
                agenda_items=agenda_items,
                documents=documents,
                html_content=html_path
            )
            
            self.save_meeting_json(meeting)
            self.scraped_urls.add(url)
            
            return meeting
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def scrape(self) -> List[ScrapedMeeting]:
        """Scrapt alle Meetings"""
        
        logger.info(f"Starting ALLRIS scraper for {self.config.base_url}")
        
        meeting_urls = self.find_meeting_links()
        logger.info(f"Found {len(meeting_urls)} meetings to scrape")
        
        meetings = []
        
        for url in tqdm(meeting_urls, desc="Scraping meetings"):
            if url in self.scraped_urls:
                logger.debug(f"Skipping already scraped: {url}")
                continue
            
            meeting = self.scrape_meeting(url)
            if meeting:
                meetings.append(meeting)
            
            # Fortschritt speichern alle 10 Meetings
            if len(meetings) % 10 == 0:
                self.save_progress()
        
        self.save_progress()
        logger.info(f"Scraping complete: {len(meetings)} meetings scraped")
        
        return meetings


class SessionNetScraper(BaseRISScraper):
    """Scraper für SessionNet (STERNBERG) Systeme"""
    
    def find_meeting_links(self) -> List[str]:
        """Findet Meeting-Links in SessionNet"""
        
        logger.info("Searching for meeting links in SessionNet...")
        
        # SessionNet hat typischerweise eine Sitzungsübersicht
        search_urls = [
            f"{self.config.base_url}/bi/si010.asp",
            f"{self.config.base_url}/bi/si020.asp",
            f"{self.config.base_url}/sessionnetbi/",
        ]
        
        meeting_links = []
        
        for search_url in search_urls:
            try:
                response = self.client.get(search_url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # SessionNet Links oft zu meetingdetail.php oder si-info
                for link in soup.find_all('a', href=re.compile(r'meetingdetail|si-info|getfile')):
                    href = link.get('href')
                    if href:
                        full_url = urljoin(self.config.base_url, href)
                        if full_url not in self.scraped_urls:
                            meeting_links.append(full_url)
                
                logger.info(f"Found {len(meeting_links)} meeting links from {search_url}")
                
            except Exception as e:
                logger.error(f"Error searching {search_url}: {e}")
                continue
        
        return list(set(meeting_links))[:self.config.max_pages]
    
    def scrape_meeting(self, url: str) -> Optional[ScrapedMeeting]:
        """Scrapt SessionNet Meeting"""
        
        try:
            response = self.client.get(url)
            soup = BeautifulSoup(response.text, 'lxml')
            
            # SessionNet hat oft ähnliche Struktur wie ALLRIS
            # Hier würde die SessionNet-spezifische Logik kommen
            
            # Für jetzt: Generic Parsing
            title = soup.find('h1')
            title = title.get_text(strip=True) if title else None
            
            html_path = self.save_html(url, response.text)
            
            meeting = ScrapedMeeting(
                url=url,
                title=title or "SessionNet Meeting",
                html_content=html_path
            )
            
            self.save_meeting_json(meeting)
            self.scraped_urls.add(url)
            
            return meeting
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None
    
    def scrape(self) -> List[ScrapedMeeting]:
        """Hauptscraping-Methode"""
        
        logger.info(f"Starting SessionNet scraper for {self.config.base_url}")
        
        meeting_urls = self.find_meeting_links()
        meetings = []
        
        for url in tqdm(meeting_urls, desc="Scraping meetings"):
            if url in self.scraped_urls:
                continue
            
            meeting = self.scrape_meeting(url)
            if meeting:
                meetings.append(meeting)
            
            if len(meetings) % 10 == 0:
                self.save_progress()
        
        self.save_progress()
        return meetings


class GenericRISScraper(BaseRISScraper):
    """Generic Scraper für unbekannte RIS-Systeme"""
    
    def scrape(self) -> List[ScrapedMeeting]:
        """Basis-Scraping: Findet alle internen Links und speichert HTML"""
        
        logger.info(f"Starting generic scraper for {self.config.base_url}")
        logger.warning("Using generic scraper - results may be less structured")
        
        visited = set()
        to_visit = [self.config.base_url]
        meetings = []
        
        pbar = tqdm(total=self.config.max_pages, desc="Scraping pages")
        
        while to_visit and len(visited) < self.config.max_pages:
            url = to_visit.pop(0)
            
            if url in visited:
                continue
            
            try:
                response = self.client.get(url)
                soup = BeautifulSoup(response.text, 'lxml')
                
                # Heuristik: Ist das eine Meeting-Seite?
                is_meeting = False
                keywords = ['sitzung', 'tagesordnung', 'agenda', 'meeting', 'gremium']
                
                page_text = soup.get_text().lower()
                if any(kw in page_text for kw in keywords):
                    is_meeting = True
                
                if is_meeting:
                    # Speichere als Meeting
                    html_path = self.save_html(url, response.text)
                    
                    title = soup.find('h1')
                    title = title.get_text(strip=True) if title else None
                    
                    meeting = ScrapedMeeting(
                        url=url,
                        title=title or "Generic Meeting",
                        html_content=html_path
                    )
                    
                    self.save_meeting_json(meeting)
                    meetings.append(meeting)
                
                # Finde weitere interne Links
                base_domain = urlparse(self.config.base_url).netloc
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    full_url = urljoin(url, href)
                    
                    # Nur interne Links
                    if urlparse(full_url).netloc == base_domain:
                        if full_url not in visited and full_url not in to_visit:
                            to_visit.append(full_url)
                
                visited.add(url)
                pbar.update(1)
                
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                continue
        
        pbar.close()
        logger.info(f"Generic scraping complete: {len(meetings)} potential meetings found")
        
        return meetings


# ==================== SCRAPER FACTORY ====================

class RISScraperFactory:
    """Factory für RIS-Scraper"""
    
    SCRAPERS = {
        'allris': ALLRISScraper,
        'sessionnet': SessionNetScraper,
        'generic': GenericRISScraper,
    }
    
    @classmethod
    def create(cls, config: ScraperConfig) -> BaseRISScraper:
        """Erstellt passenden Scraper"""
        
        # Auto-detect RIS type wenn nicht angegeben
        if config.ris_type is None:
            logger.info("Auto-detecting RIS type...")
            client = RobustHTTPClient(config)
            response = client.get(config.base_url)
            
            config.ris_type = RISTypeDetector.detect(response.text, config.base_url)
        
        scraper_class = cls.SCRAPERS.get(config.ris_type, GenericRISScraper)
        logger.info(f"Using scraper: {scraper_class.__name__}")
        
        return scraper_class(config)


# ==================== MAIN CLI ====================

def main():
    """CLI Interface"""
    
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Web Scraper für Ratsinformationssysteme"
    )
    
    parser.add_argument(
        'url',
        help='Basis-URL des Ratsinformationssystems'
    )
    
    parser.add_argument(
        '-o', '--output',
        default='./scraped_data',
        help='Output-Verzeichnis (default: ./scraped_data)'
    )
    
    parser.add_argument(
        '-n', '--max-pages',
        type=int,
        default=50,
        help='Maximale Anzahl zu scrapender Seiten (default: 50)'
    )
    
    parser.add_argument(
        '-r', '--rate-limit',
        type=float,
        default=1.0,
        help='Pause zwischen Requests in Sekunden (default: 1.0)'
    )
    
    parser.add_argument(
        '--ris-type',
        choices=['allris', 'sessionnet', 'generic'],
        help='RIS-Typ (wenn bekannt, sonst auto-detect)'
    )
    
    parser.add_argument(
        '--date-from',
        help='Nur Sitzungen ab diesem Datum (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '--date-to',
        help='Nur Sitzungen bis zu diesem Datum (YYYY-MM-DD)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Ausführliche Ausgabe'
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Config erstellen
    config = ScraperConfig(
        base_url=args.url,
        output_dir=args.output,
        max_pages=args.max_pages,
        rate_limit_seconds=args.rate_limit,
        ris_type=args.ris_type,
        date_from=args.date_from,
        date_to=args.date_to
    )
    
    # Scraper erstellen und ausführen
    scraper = RISScraperFactory.create(config)
    meetings = scraper.scrape()
    
    # Summary
    print("\n" + "="*60)
    print("SCRAPING ABGESCHLOSSEN")
    print("="*60)
    print(f"Gesamt gescrapte Meetings: {len(meetings)}")
    print(f"Output-Verzeichnis: {config.output_dir}")
    print("\nDateien:")
    print(f"  - HTML: {config.output_dir}/html/")
    print(f"  - JSON: {config.output_dir}/json/")
    print(f"  - Progress: {config.output_dir}/scraping_progress.json")
    print("="*60)


if __name__ == "__main__":
    main()
