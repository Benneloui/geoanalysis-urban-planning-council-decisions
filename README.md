# Spatial-Temporal Analysis of Council Decisions on Development Plans

## 📋 Project Proposal

See detailed project proposal: [PROPOSAL.md](PROPOSAL.md)

---

## Project Overview

This project investigates the spatial and temporal patterns of municipal council decisions related to development plans (Bebauungspläne) in [CITY X]. Using council meeting information combined with development plan geodata, we analyze where and when planning decisions occur over a [TIME PERIOD] period.

---

## Research Questions

> **"Where and when are development plans (Bebauungspläne) politically negotiated in [CITY]?"**


---

## Project Structure

```
├── README.md                      <- This file: project overview and instructions
├── PROPOSAL.md                    <- Detailed project proposal
│
├── council_decisions_analysis.Rproj  <- R project file
│
├── .gitignore                     <- Files to exclude from version control
├── renv.lock                      <- Package dependency lock file
│
├── data-raw/                      <- Raw data from external sources (NOT in git)
│   ├── README.md                  <- Data collection protocol
│   ├── council_meetings/          <- Downloaded council information
│   └── geodata/                   <- Shapefiles, GeoJSON files
│
├── data/                          <- Processed, analysis-ready data (IN git)
│   ├── README.md                  <- Data dictionary
│   ├── council_bplan_decisions.csv       <- Main analysis dataset
│   ├── council_bplan_decisions.geojson   <- Georeferenced decisions
│   └── districts.geojson                 <- District boundaries
│
├── R/                             <- Custom R functions
│   ├── load_data.R                <- Data loading utilities
│   ├── geocoding.R                <- Geocoding functions
│   ├── spatial_analysis.R         <- Moran's I, clustering functions
│   └── visualization.R            <- Custom plotting functions
│
├── analysis/                      <- Analysis scripts (numbered workflow)
│   ├── 01_data_processing.R
│   └── 02
│
├── vignettes/                     <- R Markdown reports
│   ├── analysis.Rmd               <- Main report (full workflow)
│   ├── references.bib             <- Bibliography
│   └── apa-7th-edition.csl        <- Citation style
│
├── outputs/                       <- Generated outputs (NOT in git)
│   ├── figures/                   <- All plots and maps
│   └── tables/                    <- Results tables
│
└── figures/                       <- Publication-ready figures (IN git)
    ├── fig1_overview_map.png
    ├── fig2_temporal_trend.png
    ├── fig3_spatial_clusters.png
    ├── fig4_thematic_distribution.png
    └── fig5_renewal_comparison.png
```

---

## Dependencies

---

## License

- **Code:** MIT License
- **Documentation:** CC-BY 4.0

---

## Contact

**Author:** [Your Name]
**Email:** [your.email@unibe.ch]

---

## Acknowledgments

---

## Key References



[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![R Version](https://img.shields.io/badge/R-%3E%3D%204.3.0-blue.svg)](https://www.r-project.org/)