#!/usr/bin/env python3
"""
Installations-Check für Smart Location Extractor
================================================

Prüft ob alle benötigten Pakete installiert sind:
- spacy (NER)
- thefuzz (Fuzzy Matching)
- python-Levenshtein (Performance-Boost für thefuzz)
- PyMuPDF (PDF Text-Extraktion)
"""

import sys

def check_package(name, import_name=None):
    """Prüft ob ein Paket installiert ist"""
    if import_name is None:
        import_name = name

    try:
        __import__(import_name)
        print(f"✅ {name} ist installiert")
        return True
    except ImportError:
        print(f"❌ {name} fehlt - bitte installieren")
        return False

def main():
    print("=" * 60)
    print("SMART LOCATION EXTRACTOR - DEPENDENCY CHECK")
    print("=" * 60)
    print()

    packages = [
        ("spacy", "spacy"),
        ("thefuzz", "thefuzz"),
        ("python-Levenshtein", "Levenshtein"),
        ("PyMuPDF", "fitz"),
    ]

    all_ok = True
    for name, import_name in packages:
        if not check_package(name, import_name):
            all_ok = False

    print()

    # Prüfe spaCy Modell
    if check_package("spacy", "spacy"):
        try:
            import spacy
            nlp = spacy.load("de_core_news_sm")
            print("✅ spaCy Modell 'de_core_news_sm' ist installiert")
        except OSError:
            print("❌ spaCy Modell 'de_core_news_sm' fehlt")
            print("   Bitte ausführen: python -m spacy download de_core_news_sm")
            all_ok = False

    print()
    print("=" * 60)

    if all_ok:
        print("✅ ALLE DEPENDENCIES SIND INSTALLIERT!")
        print()
        print("Jetzt kannst du den Data Loader verwenden:")
        print("  python R/oparl_data_loader.py")
    else:
        print("⚠️  FEHLENDE DEPENDENCIES!")
        print()
        print("Installation:")
        print("  mamba activate p-grisa-env")
        print("  mamba install -y spacy thefuzz python-Levenshtein pymupdf")
        print("  python -m spacy download de_core_news_sm")

    print("=" * 60)

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
