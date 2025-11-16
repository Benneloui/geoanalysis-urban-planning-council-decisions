"""
HTML-Struktur-Analyzer für Ratsinformationssysteme
====================================================

Dieses Tool hilft Ihnen, die HTML-Struktur eines RIS zu verstehen,
bevor Sie den Scraper anpassen.

Usage:
    python analyze_ris_structure.py <URL>
"""

import requests
from bs4 import BeautifulSoup
from collections import Counter
import re
from urllib.parse import urljoin, urlparse


def analyze_ris_structure(url: str):
    """Analysiert die HTML-Struktur einer RIS-Seite"""
    
    print("="*80)
    print(f"RIS STRUKTUR-ANALYSE: {url}")
    print("="*80)
    print()
    
    # Seite laden
    response = requests.get(url, timeout=30)
    soup = BeautifulSoup(response.text, 'lxml')
    
    # 1. Basis-Informationen
    print("📄 BASIS-INFORMATIONEN")
    print("-" * 80)
    print(f"Title: {soup.title.string if soup.title else 'N/A'}")
    print(f"Encoding: {response.encoding}")
    print(f"Status: {response.status_code}")
    print()
    
    # 2. RIS-Typ-Erkennung
    print("🔍 RIS-TYP-ERKENNUNG")
    print("-" * 80)
    
    html_lower = response.text.lower()
    
    if 'allris' in html_lower or 'cc e-gov' in html_lower:
        print("✅ ALLRIS (CC e-gov) erkannt")
    elif 'sessionnet' in html_lower or 'sternberg' in html_lower:
        print("✅ SessionNet (STERNBERG) erkannt")
    elif 'esitzungsdienst' in html_lower:
        print("✅ eSitzungsdienst erkannt")
    elif 'sd.net' in html_lower:
        print("✅ sd.net RIM erkannt")
    else:
        print("⚠️  Unbekanntes RIS-System")
    
    print()
    
    # 3. Wichtige Meta-Tags
    print("🏷️  META-TAGS")
    print("-" * 80)
    for meta in soup.find_all('meta')[:10]:
        name = meta.get('name') or meta.get('property') or meta.get('http-equiv')
        content = meta.get('content', '')
        if name:
            print(f"  {name}: {content[:80]}")
    print()
    
    # 4. Haupt-Container
    print("📦 HAUPT-CONTAINER")
    print("-" * 80)
    
    # Häufigste IDs
    ids = [elem.get('id') for elem in soup.find_all(id=True)]
    print("Häufigste IDs:")
    for id_name, count in Counter(ids).most_common(10):
        print(f"  #{id_name}: {count}x")
    print()
    
    # Häufigste Classes
    classes = []
    for elem in soup.find_all(class_=True):
        classes.extend(elem.get('class', []))
    
    print("Häufigste CSS-Klassen:")
    for class_name, count in Counter(classes).most_common(15):
        print(f"  .{class_name}: {count}x")
    print()
    
    # 5. Tabellen-Struktur
    print("📊 TABELLEN")
    print("-" * 80)
    tables = soup.find_all('table')
    print(f"Anzahl Tabellen: {len(tables)}")
    
    for idx, table in enumerate(tables[:5], 1):
        print(f"\nTabelle {idx}:")
        print(f"  ID: {table.get('id', 'N/A')}")
        print(f"  Class: {' '.join(table.get('class', []))}")
        
        rows = table.find_all('tr')
        print(f"  Zeilen: {len(rows)}")
        
        if rows:
            headers = rows[0].find_all(['th', 'td'])
            print(f"  Spalten in erster Zeile: {len(headers)}")
            if headers:
                print(f"  Header-Texte: {[h.get_text(strip=True)[:30] for h in headers[:5]]}")
    
    print()
    
    # 6. Links & Navigation
    print("🔗 LINKS & NAVIGATION")
    print("-" * 80)
    
    all_links = soup.find_all('a', href=True)
    print(f"Gesamt Links: {len(all_links)}")
    
    # Gruppiere Links nach Pattern
    link_patterns = Counter()
    for link in all_links:
        href = link.get('href', '')
        
        # Extrahiere Pattern (Dateiname ohne Parameter)
        if '?' in href:
            pattern = href.split('?')[0]
        else:
            pattern = href
        
        # Nur Basename
        pattern = pattern.split('/')[-1] if '/' in pattern else pattern
        link_patterns[pattern] += 1
    
    print("\nHäufigste Link-Patterns:")
    for pattern, count in link_patterns.most_common(15):
        if pattern:
            print(f"  {pattern}: {count}x")
    print()
    
    # Sitzungs-Links
    meeting_keywords = ['sitzung', 'meeting', 'si-info', 'meetingdetail', 'session']
    meeting_links = []
    
    for link in all_links[:50]:  # Erste 50 Links
        href = link.get('href', '')
        text = link.get_text(strip=True)
        
        if any(kw in href.lower() or kw in text.lower() for kw in meeting_keywords):
            full_url = urljoin(url, href)
            meeting_links.append((text[:60], full_url))
    
    if meeting_links:
        print(f"🎯 Potenzielle Sitzungs-Links (erste 10):")
        for text, link in meeting_links[:10]:
            print(f"  '{text}' -> {link}")
        print()
    
    # 7. Formular-Analyse
    print("📝 FORMULARE")
    print("-" * 80)
    
    forms = soup.find_all('form')
    print(f"Anzahl Formulare: {len(forms)}")
    
    for idx, form in enumerate(forms, 1):
        print(f"\nFormular {idx}:")
        print(f"  Action: {form.get('action', 'N/A')}")
        print(f"  Method: {form.get('method', 'GET')}")
        
        inputs = form.find_all('input')
        print(f"  Input-Felder: {len(inputs)}")
        
        for inp in inputs[:10]:
            inp_type = inp.get('type', 'text')
            inp_name = inp.get('name', 'N/A')
            print(f"    - {inp_type}: {inp_name}")
    
    print()
    
    # 8. JavaScript-Analyse
    print("⚙️  JAVASCRIPT")
    print("-" * 80)
    
    scripts = soup.find_all('script', src=True)
    print(f"Externe Scripts: {len(scripts)}")
    
    for script in scripts[:5]:
        src = script.get('src')
        print(f"  {src}")
    
    inline_scripts = soup.find_all('script', src=False)
    print(f"\nInline Scripts: {len(inline_scripts)}")
    
    print()
    
    # 9. Datumsformate erkennen
    print("📅 DATUMSFORMATE")
    print("-" * 80)
    
    page_text = soup.get_text()
    
    date_patterns = {
        'DD.MM.YYYY': r'\d{2}\.\d{2}\.\d{4}',
        'DD.MM.YY': r'\d{2}\.\d{2}\.\d{2}',
        'YYYY-MM-DD': r'\d{4}-\d{2}-\d{2}',
        'D. Monat YYYY': r'\d{1,2}\.\s*\w+\s*\d{4}',
    }
    
    for pattern_name, pattern in date_patterns.items():
        matches = re.findall(pattern, page_text)
        if matches:
            print(f"  {pattern_name}: {len(matches)}x gefunden")
            print(f"    Beispiele: {matches[:3]}")
    
    print()
    
    # 10. Empfehlungen
    print("💡 EMPFEHLUNGEN")
    print("=" * 80)
    
    print("\n1. Scraper-Konfiguration:")
    print(f"   base_url: {url}")
    
    if 'allris' in html_lower:
        print("   ris_type: allris")
        print("   Startseite für Sitzungen: /si-info.asp oder /si020.asp")
    elif 'sessionnet' in html_lower:
        print("   ris_type: sessionnet")
        print("   Startseite für Sitzungen: /bi/si010.asp")
    else:
        print("   ris_type: generic")
    
    print("\n2. Wichtige Selektoren:")
    
    h1 = soup.find('h1')
    if h1:
        print(f"   Titel: h1 (Beispiel: '{h1.get_text(strip=True)[:50]}')")
    
    if tables:
        main_table = tables[0]
        table_class = ' '.join(main_table.get('class', []))
        print(f"   Haupt-Tabelle: table.{table_class}" if table_class else "   Haupt-Tabelle: table")
    
    print("\n3. Nächste Schritte:")
    print("   - Passen Sie ris_scraper.py an die gefundenen Selektoren an")
    print("   - Testen Sie mit: python ris_scraper.py <URL> -n 5")
    print("   - Prüfen Sie die gespeicherten HTML-Dateien")
    
    print()
    print("="*80)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python analyze_ris_structure.py <URL>")
        print("\nBeispiele:")
        print("  python analyze_ris_structure.py https://ratsinfo.beispielstadt.de")
        print("  python analyze_ris_structure.py https://sessionnet.beispielstadt.de/bi/")
        sys.exit(1)
    
    url = sys.argv[1]
    
    try:
        analyze_ris_structure(url)
    except Exception as e:
        print(f"\n❌ Fehler: {e}")
        import traceback
        traceback.print_exc()
