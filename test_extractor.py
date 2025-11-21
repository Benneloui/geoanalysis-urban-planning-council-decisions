#!/usr/bin/env python3
"""Quick test script for location extractor without OSM"""
import sys
sys.path.insert(0, 'R')

# Test just the import
print("Testing import...")
try:
    from location_extractor import AugsburgLocationExtractor
    print("✓ Import successful!")

    print("\nInitializing extractor (this will fetch OSM data)...")
    extractor = AugsburgLocationExtractor()

    print(f"✓ Extractor loaded with {len(extractor.streets)} streets")

    # Test extraction
    test_text = "Sanierung der Maximilianstraße und Pläne für den Königsplatz"
    print(f"\nTest input: '{test_text}'")
    locations = extractor.get_locations_from_text(test_text)
    print(f"Found locations: {locations}")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
