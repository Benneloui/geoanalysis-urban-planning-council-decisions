#!/bin/bash

# Quick Start Script für RIS Scraper
# ===================================
# Führt Sie Schritt für Schritt durch den ersten Scraping-Prozess

set -e  # Exit on error

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  🕷️  RIS Web Scraper - Quick Start"
echo "════════════════════════════════════════════════════════════"
echo ""

# 1. Check Dependencies
echo -e "${BLUE}📦 Schritt 1: Prüfe Dependencies...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 nicht gefunden!${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python 3: $(python3 --version)${NC}"

# Check pip packages
echo "Prüfe Python-Pakete..."
MISSING=()

for pkg in requests beautifulsoup4 lxml tqdm pyyaml; do
    if ! python3 -c "import ${pkg//-/_}" 2>/dev/null; then
        MISSING+=("$pkg")
    fi
done

if [ ${#MISSING[@]} -ne 0 ]; then
    echo -e "${YELLOW}⚠️  Fehlende Pakete: ${MISSING[*]}${NC}"
    echo ""
    read -p "Möchten Sie diese jetzt installieren? (j/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        pip3 install requests beautifulsoup4 lxml tqdm pyyaml
        echo -e "${GREEN}✅ Pakete installiert${NC}"
    else
        echo -e "${RED}Bitte installieren Sie die Pakete manuell:${NC}"
        echo "  pip3 install requests beautifulsoup4 lxml tqdm pyyaml"
        exit 1
    fi
else
    echo -e "${GREEN}✅ Alle Python-Pakete vorhanden${NC}"
fi

echo ""

# 2. URL eingeben
echo -e "${BLUE}🌐 Schritt 2: RIS-URL eingeben${NC}"
echo "Beispiele:"
echo "  - https://risi.muenchen.de/risi"
echo "  - https://ratsinformation.stadt-koeln.de"
echo "  - https://ratsinfo.IhreStadt.de"
echo ""

read -p "Ihre RIS-URL: " RIS_URL

if [ -z "$RIS_URL" ]; then
    echo -e "${RED}❌ Keine URL eingegeben${NC}"
    exit 1
fi

echo -e "${GREEN}✅ URL: $RIS_URL${NC}"
echo ""

# 3. Struktur analysieren
echo -e "${BLUE}🔍 Schritt 3: HTML-Struktur analysieren...${NC}"
echo "Dies dauert einen Moment..."
echo ""

if python3 analyze_ris_structure.py "$RIS_URL"; then
    echo ""
    echo -e "${GREEN}✅ Struktur-Analyse abgeschlossen${NC}"
    echo ""
    
    read -p "Analyse in Datei speichern? (j/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Jj]$ ]]; then
        ANALYSIS_FILE="ris_analysis_$(date +%Y%m%d_%H%M%S).txt"
        python3 analyze_ris_structure.py "$RIS_URL" > "$ANALYSIS_FILE"
        echo -e "${GREEN}✅ Gespeichert in: $ANALYSIS_FILE${NC}"
    fi
else
    echo -e "${RED}❌ Analyse fehlgeschlagen${NC}"
    echo "Prüfen Sie die URL und Ihre Internetverbindung"
    exit 1
fi

echo ""

# 4. Test-Scrape
echo -e "${BLUE}🧪 Schritt 4: Test-Scrape (5 Seiten)${NC}"
echo ""

read -p "Test-Scrape starten? (j/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Jj]$ ]]; then
    echo "Übersprungen. Sie können später manuell scrapen mit:"
    echo "  python3 ris_scraper.py \"$RIS_URL\" -n 5 -v"
    exit 0
fi

echo ""
echo "Starte Test-Scrape (nur 5 Seiten)..."
echo ""

TEST_OUTPUT="./test_scrape_$(date +%Y%m%d_%H%M%S)"

if python3 ris_scraper.py "$RIS_URL" -n 5 -o "$TEST_OUTPUT" -v; then
    echo ""
    echo -e "${GREEN}✅ Test-Scrape erfolgreich!${NC}"
    echo ""
    echo "Ergebnisse:"
    echo "  📁 Output-Verzeichnis: $TEST_OUTPUT"
    
    HTML_COUNT=$(find "$TEST_OUTPUT/html" -name "*.html" 2>/dev/null | wc -l)
    JSON_COUNT=$(find "$TEST_OUTPUT/json" -name "*.json" 2>/dev/null | wc -l)
    
    echo "  📄 HTML-Dateien: $HTML_COUNT"
    echo "  📋 JSON-Dateien: $JSON_COUNT"
    
    if [ $JSON_COUNT -gt 0 ]; then
        echo ""
        echo "Beispiel-Meeting:"
        FIRST_JSON=$(find "$TEST_OUTPUT/json" -name "*.json" | head -1)
        if command -v jq &> /dev/null; then
            cat "$FIRST_JSON" | jq '.title, .date, .location'
        else
            head -10 "$FIRST_JSON"
        fi
    fi
    
else
    echo -e "${RED}❌ Test-Scrape fehlgeschlagen${NC}"
    echo "Mögliche Ursachen:"
    echo "  - URL nicht erreichbar"
    echo "  - RIS-System blockiert Scraping"
    echo "  - HTML-Struktur nicht erkannt"
    echo ""
    echo "Versuchen Sie:"
    echo "  - Rate Limit erhöhen: -r 2.0"
    echo "  - RIS-Typ manuell angeben: --ris-type allris"
    exit 1
fi

echo ""

# 5. Nächste Schritte
echo -e "${BLUE}🎯 Schritt 5: Nächste Schritte${NC}"
echo ""
echo "Der Test war erfolgreich! Nächste Schritte:"
echo ""
echo "1. Prüfen Sie die Test-Ergebnisse:"
echo "   cd $TEST_OUTPUT"
echo "   ls -la html/"
echo "   cat json/meeting_*.json"
echo ""
echo "2. Falls die Daten nicht korrekt sind:"
echo "   - Öffnen Sie ris_scraper.py"
echo "   - Passen Sie die Selektoren an (siehe SCRAPER_README.md)"
echo "   - Nutzen Sie die Analyse-Ausgabe als Referenz"
echo ""
echo "3. Vollständiges Scraping starten:"
echo "   python3 ris_scraper.py \"$RIS_URL\" -n 100 -o ./scraped_data"
echo ""
echo "4. Integration mit ETL-Pipeline:"
echo "   python3 stadtrat_etl_pipeline.py"
echo ""
echo -e "${GREEN}✨ Quick Start abgeschlossen!${NC}"
echo ""
echo "Weitere Hilfe:"
echo "  📖 Siehe SCRAPER_README.md"
echo "  🐛 Bei Problemen: python3 ris_scraper.py --help"
echo ""
