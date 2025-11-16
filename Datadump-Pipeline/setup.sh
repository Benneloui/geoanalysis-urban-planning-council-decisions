#!/bin/bash

# Stadtratssitzungs ETL-Pipeline - Setup Script
# =============================================

echo "🚀 Stadtratssitzungs ETL-Pipeline Setup"
echo "========================================"
echo ""

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fehlerbehandlung
set -e
trap 'echo -e "${RED}❌ Fehler bei Zeile $LINENO${NC}"' ERR

# 1. Python Virtual Environment
echo -e "${YELLOW}📦 Erstelle Python Virtual Environment...${NC}"
python3 -m venv venv
source venv/bin/activate

# 2. Dependencies installieren
echo -e "${YELLOW}📥 Installiere Python-Abhängigkeiten...${NC}"
pip install --upgrade pip
pip install -r requirements.txt

# 3. spaCy Modell herunterladen
echo -e "${YELLOW}🧠 Lade spaCy NER-Modell herunter...${NC}"
python -m spacy download de_core_news_lg

# 4. PostgreSQL Check
echo -e "${YELLOW}🔍 Prüfe PostgreSQL Installation...${NC}"
if command -v psql &> /dev/null; then
    echo -e "${GREEN}✅ PostgreSQL ist installiert${NC}"
    PSQL_VERSION=$(psql --version | awk '{print $3}')
    echo "   Version: $PSQL_VERSION"
else
    echo -e "${RED}❌ PostgreSQL nicht gefunden!${NC}"
    echo "   Installiere PostgreSQL mit: sudo apt-get install postgresql-14 postgresql-14-postgis-3"
    exit 1
fi

# 5. Verzeichnisstruktur erstellen
echo -e "${YELLOW}📁 Erstelle Verzeichnisstruktur...${NC}"
mkdir -p data/html_dump
mkdir -p data/documents
mkdir -p logs
mkdir -p tests

echo -e "${GREEN}✅ Verzeichnisse erstellt${NC}"

# 6. Datenbank Setup
echo -e "${YELLOW}🗄️  Datenbank Setup...${NC}"
read -p "Möchten Sie die Datenbank jetzt einrichten? (j/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Jj]$ ]]; then
    read -p "PostgreSQL Benutzername [postgres]: " DB_USER
    DB_USER=${DB_USER:-postgres}
    
    read -p "Datenbankname [stadtrat_db]: " DB_NAME
    DB_NAME=${DB_NAME:-stadtrat_db}
    
    # Datenbank erstellen
    echo "Erstelle Datenbank $DB_NAME..."
    sudo -u postgres createdb $DB_NAME || echo "Datenbank existiert bereits"
    
    # Schema laden
    echo "Lade Schema..."
    sudo -u postgres psql -d $DB_NAME -f schema_stadtrat.sql
    
    echo -e "${GREEN}✅ Datenbank eingerichtet${NC}"
else
    echo "Überspringe Datenbank-Setup"
    echo "Führe später manuell aus: psql -d stadtrat_db -f schema_stadtrat.sql"
fi

# 7. Config anpassen
echo -e "${YELLOW}⚙️  Konfiguration...${NC}"
if [ ! -f config.yaml ]; then
    echo "config.yaml existiert bereits"
else
    echo "Bitte passe config.yaml an deine Umgebung an:"
    echo "  - Database Credentials"
    echo "  - HTML Dump Verzeichnis"
    echo "  - Stadt-Name für Geocoding"
fi

# 8. Test-Run
echo -e "${YELLOW}🧪 Test-Konfiguration...${NC}"
python -c "
from stadtrat_etl_pipeline import DatabaseLoader
import yaml

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

try:
    loader = DatabaseLoader(config['database'])
    print('✅ Datenbankverbindung erfolgreich')
except Exception as e:
    print(f'❌ Datenbankverbindung fehlgeschlagen: {e}')
" || echo "Bitte config.yaml anpassen und erneut testen"

# Fertig!
echo ""
echo -e "${GREEN}✨ Setup abgeschlossen!${NC}"
echo ""
echo "Nächste Schritte:"
echo "1. Passe config.yaml an deine Umgebung an"
echo "2. Lege HTML-Dumps in ./data/html_dump/"
echo "3. Führe Pipeline aus: python stadtrat_etl_pipeline.py"
echo ""
echo "Dokumentation: Siehe README.md"
echo ""
