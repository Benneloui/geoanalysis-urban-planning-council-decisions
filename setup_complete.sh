#!/bin/bash
cd /Users/benedikt.pilgram/Code/Geomodelierung

# Erstelle alle Ordner
mkdir -p data-raw/{council_meetings,geodata/{bplaene,renewal_areas,districts,context},scripts}
mkdir -p data
mkdir -p R
mkdir -p analysis
mkdir -p vignettes
mkdir -p outputs/{figures,tables,models}
mkdir -p figures
mkdir -p docs
mkdir -p presentations

# Erstelle Placeholder-Dateien (damit Git die leeren Ordner tracked)
touch data-raw/.gitkeep
touch data/.gitkeep
touch R/.gitkeep
touch analysis/.gitkeep
touch vignettes/.gitkeep
touch figures/.gitkeep
touch docs/.gitkeep
touch presentations/.gitkeep

# Erstelle wichtige README Dateien
cat > data/README.md << 'EOF'
# Data Directory

This folder contains processed, analysis-ready data.

## Files (to be created):
- `council_bplan_decisions.csv` - Main analysis dataset
- `council_bplan_decisions.geojson` - Georeferenced version
- `districts.geojson` - District boundaries

Run processing scripts to generate these files.
EOF

cat > data-raw/README.md << 'EOF'
# Raw Data Directory

**Note:** This folder is not tracked in Git (.gitignore).

Place raw data files here:
- Council meeting documents (PDFs/JSON)
- Original shapefiles
- Downloaded geodata

See `scripts/` folder for data collection scripts.
EOF

cat > R/README.md << 'EOF'
# R Functions

Custom R functions for the project.

Files:
- `load_data.R` - Data loading utilities
- `spatial_analysis.R` - Spatial statistics functions
- `visualization.R` - Plotting functions
- `utils.R` - Helper functions
EOF

cat > analysis/README.md << 'EOF'
# Analysis Scripts

Numbered workflow scripts:

1. `01_data_processing.R` - Text extraction, geocoding
2. `02_exploratory_analysis.R` - Descriptive statistics
3. `03_temporal_analysis.R` - Time series analysis
4. `04_spatial_clustering.R` - Moran's I, LISA
5. `05_thematic_analysis.R` - Topic categorization
6. `06_renewal_comparison.R` - Urban renewal analysis (optional)

Run in order.
EOF

cat > vignettes/README.md << 'EOF'
# Analysis Reports

- `analysis.Rmd` - Main report (full workflow)
- `references.bib` - Bibliography
- `apa-7th-edition.csl` - Citation style
EOF

# Erstelle .gitkeep für outputs (damit Ordner existiert aber Inhalt ignoriert wird)
touch outputs/.gitkeep

echo "✅ Project structure created!"