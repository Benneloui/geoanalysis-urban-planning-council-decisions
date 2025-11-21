import requests
import spacy
from thefuzz import process, fuzz
import pandas as pd
import os

class AugsburgLocationExtractor:
    def __init__(self, osm_cache_path='data-raw/augsburg_streets.csv'):
        self.osm_cache_path = osm_cache_path
        self.streets = self._load_or_fetch_osm_streets()

        # Lade deutsches KI-Modell für Textverständnis
        print("Lade spaCy NLP Modell...")
        try:
            self.nlp = spacy.load("de_core_news_sm")
        except:
            print("⚠️ Modell nicht gefunden. Bitte ausführen: python -m spacy download de_core_news_sm")
            self.nlp = None

    def _load_or_fetch_osm_streets(self):
        """Holt die 'Ground Truth': Alle Straßennamen in Augsburg."""
        if os.path.exists(self.osm_cache_path):
            print(f"Lade Straßenverzeichnis aus Cache ({self.osm_cache_path})...")
            return pd.read_csv(self.osm_cache_path)['name'].tolist()

        print("Lade Straßenverzeichnis frisch von OpenStreetMap (Overpass API)...")
        # Query: Alle Straßen (highway) in der Relation Augsburg (admin_level=6)
        query = """
        [out:json];
        area["name"="Augsburg"]["admin_level"="6"]->.searchArea;
        (
          way["highway"]["name"](area.searchArea);
        );
        out body;
        """
        try:
            resp = requests.get("http://overpass-api.de/api/interpreter", params={'data': query})
            data = resp.json()
            streets = sorted(list(set([e['tags']['name'] for e in data['elements'] if 'tags' in e and 'name' in e['tags']])))

            # Cache speichern
            os.makedirs(os.path.dirname(self.osm_cache_path), exist_ok=True)
            pd.DataFrame({'name': streets}).to_csv(self.osm_cache_path, index=False)
            print(f"✓ {len(streets)} Straßen gefunden und gespeichert.")
            return streets
        except Exception as e:
            print(f"❌ Fehler bei OSM Abfrage: {e}")
            return []

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

    def get_locations_from_text(self, text):
        """Hauptfunktion für die Pipeline"""
        if not isinstance(text, str) or not text:
            return []

        # 1. Kandidaten finden
        candidates = self.extract_candidates(text)

        # 2. Validieren
        if candidates:
            return self.validate_and_clean(candidates)
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
