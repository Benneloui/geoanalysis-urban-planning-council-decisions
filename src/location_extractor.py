import requests
import spacy
from thefuzz import process, fuzz
import pandas as pd
import json
import os
from pathlib import Path

_FILE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = _FILE_DIR.parent
DEFAULT_GAZETTEER = PROJECT_ROOT / 'data' / 'gazetteer' / 'streets.geojson'

class AugsburgLocationExtractor:
    def __init__(self, gazetteer_path=None):
        # Use the GeoJSON gazetteer instead of CSV
        self.gazetteer_path = str((Path(gazetteer_path).resolve() if gazetteer_path else DEFAULT_GAZETTEER))
        self.streets = self._load_gazetteer_streets()
        self.street_coords = self._load_street_coordinates()

        # Load German NLP model
        print("Lade spaCy NLP Modell...")
        try:
            self.nlp = spacy.load("de_core_news_sm")
        except:
            print("⚠️ Modell nicht gefunden. Bitte ausführen: python -m spacy download de_core_news_sm")
            self.nlp = None

    def _load_gazetteer_streets(self):
        """Load street names from GeoJSON gazetteer."""
        if os.path.exists(self.gazetteer_path):
            print(f"Lade Straßenverzeichnis aus Gazetteer ({self.gazetteer_path})...")
            try:
                with open(self.gazetteer_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                streets = []
                for feature in data.get('features', []):
                    props = feature.get('properties', {})
                    if 'name' in props:
                        streets.append(props['name'])

                streets = sorted(list(set(streets)))  # Deduplicate and sort
                print(f"✓ {len(streets)} Straßen gefunden und geladen.")
                return streets
            except Exception as e:
                print(f"⚠️ Gazetteer konnte nicht gelesen werden ({e})")

        print("⚠️ Gazetteer nicht vorhanden. Bitte führen Sie aus: python scripts/00_setup_city.py")
        return []

    def _load_street_coordinates(self):
        """Load street coordinates from GeoJSON for enrichment."""
        coords = {}
        if os.path.exists(self.gazetteer_path):
            try:
                with open(self.gazetteer_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for feature in data.get('features', []):
                    props = feature.get('properties', {})
                    geom = feature.get('geometry', {})

                    if 'name' in props and geom.get('type') == 'Point':
                        coords_list = geom.get('coordinates', [])
                        if len(coords_list) == 2:
                            coords[props['name'].lower()] = {
                                'lon': coords_list[0],
                                'lat': coords_list[1]
                            }
            except Exception as e:
                print(f"⚠️ Koordinaten konnten nicht geladen werden: {e}")

        return coords

    def extract_candidates(self, text):
        """Schritt 1: Kandidaten finden (NER + Regex)"""
        candidates = set()

        # A. SpaCy NER (Erkennt 'Am Königsplatz' als LOC)
        if self.nlp:
            doc = self.nlp(text)
            for ent in doc.ents:
                if ent.label_ == "LOC": # Location
                    candidates.add(ent.text)

        # B. Fallback: Einfache Suche nach Schlüsselwörtern, falls NER versagt
        keywords = ["straße", "platz", "allee", "weg", "gasse"]
        words = text.replace(",", "").split()
        for word in words:
            for kw in keywords:
                if kw in word.lower() and len(word) > 4: # Ignoriere kurze Schnipsel
                    candidates.add(word)

        return list(candidates)

    def validate_and_clean(self, candidates, threshold=85):
        """Schritt 2: Abgleich gegen echte Augsburger Straßen (Fuzzy)"""
        valid_locations = []

        for candidate in candidates:
            # Säubern (z.B. "in der Maximilianstraße" -> "Maximilianstraße")
            # Fuzzy Matching sucht den ähnlichsten Straßennamen in der OSM-Liste
            if not self.streets:
                return candidates # Fallback wenn OSM leer

            # extractOne gibt (BestMatch, Score) zurück
            best_match, score = process.extractOne(candidate, self.streets, scorer=fuzz.token_set_ratio)

            if score >= threshold:
                # Wir nehmen den SAUBEREN Namen aus OSM, nicht den dreckigen aus dem Text!
                if best_match not in valid_locations:
                    valid_locations.append(best_match)

        return valid_locations

    def get_locations_with_coordinates(self, text):
        """Return locations with pre-loaded coordinates from gazetteer (NO geocoding needed)"""
        if not isinstance(text, str) or not text:
            return []

        # 1. Kandidaten finden
        candidates = self.extract_candidates(text)

        # 2. Validieren und säubern
        if candidates:
            cleaned_locations = self.validate_and_clean(candidates)

            # 3. Füge Koordinaten aus Gazetteer hinzu (bereits geocodiert!)
            locations_with_coords = []
            for loc in cleaned_locations:
                coords = self.street_coords.get(loc.lower())
                locations_with_coords.append({
                    'name': loc,
                    'latitude': coords['lat'] if coords else None,
                    'longitude': coords['lon'] if coords else None,
                    'source': 'gazetteer'
                })
            return locations_with_coords
        return []

# --- TESTBEREICH ---
if __name__ == "__main__":
    extractor = AugsburgLocationExtractor()

    test_titles = [
        "Sanierung der Maxstr. und Pläne für den Königsplatz",
        "Bebauungsplan Nr. 10 'Östlich der Lechhauser Straße'",
        "Bericht zur Situation am Roten Tor",
        "Keine Ortsangabe hier drin"
    ]

    print("\n--- TESTLAUF ---")
    for title in test_titles:
        locs = extractor.get_locations_from_text(title)
        print(f"Input: '{title}'")
        print(f" -> Gefunden: {locs}")
