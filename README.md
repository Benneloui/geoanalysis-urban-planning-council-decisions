# Spatial-Temporal Analysis of Council Decisions on Development Plans

See detailed project proposal: [Proposal.md](Proposal.md)

This project investigates the spatial and temporal patterns of municipal council decisions related to development plans (Bebauungspläne) in City X. Using council meeting information combined with development plan geodata, we analyze where and when planning decisions occur over a TIME PERIOD period.

## Research Questions

> "Where and when is geographically relevant information, such as development plans in City X, negotiated politically? What anomalies does a spatial-temporal analysis of City Council information in period Y reveal? How does the ratio of decisions in planned and unplanned areas vary?"


## Project Structure

```
  │
  ├── 📄 README.md                       ← Project overview
  ├── 📄 Proposal.md                     ← Research proposal
  ├── 📄 LICENSE
  ├── 📄 geomodelierung.Rproj            ← RStudio project file
  ├── 📄 .gitignore                      ← Git ignore rules
  │
  ├── 📂 R/                              ← **REUSABLE FUNCTION LIBRARY**
  │   ├── README.md                      ← Documentation
  │   ├── utils.R                        ← General helpers
  │   ├── oparl_api.R                    ← OParl API integration
  │   ├── text_analysis.R                ← Text mining for B-Plans
  │   ├── geocoding.R                    ← Spatial processing
  │   └── visualization.R                ← Publication plots
  │
  ├── 📂 analysis/                       ← **PRODUCTION WORKFLOWS**
  │   ├── README.md                      ← Workflow documentation
  │   └── 01_download_data.R             ← Data collection script
  │
  ├── 📂 test_demo/                      ← **DEMO & UTILITIES**
  │   ├── demo_oparl_cologne.R              ← Proof-of-concept demo
  │   └── utils/
  │       └── synthetic_data.R           ← Test data generator
  │
  ├── 📂 data-raw/                       ← **RAW DATA** (gitignored)
  │   ├── README.md                      ← Data collection protocol
  │   └── council_meetings/              ← Downloaded OParl data (.rds files)
  │       └──
  │
  ├── 📂 data/                           ← **PROCESSED DATA** (git-tracked)
  │   ├── README.md                      ← Data dictionary
  │   └──
  │
  ├── 📂 vignettes/                      ← **R MARKDOWN REPORTS**
  │   ├── README.md                      ← Vignette documentation
  │   └── placeholder.Rmd
  │
  ├── 📂 figures/                        ← **PUBLICATION FIGURES** (git-tracked)
  │   └── (empty - ready for final figures)
  │
  ├── 📂 outputs/                        ← **WORKING OUTPUTS** (gitignored, not shown)
  │   └── figures/                       ← Generated plots during analysis
  │
  ├── 📂 docs/                           ← **DOCUMENTATION**
  │   └── (empty - ready for additional docs)
  │
  ├── 📂 presentations/                  ← **PRESENTATIONS**
  │   └── (empty - ready for slides)
  │
  └── 📂 .vscode/                        ← VSCode configuration
      └── launch.json                    ← Debug configuration

```


## Dependencies


## Contact
Benedikt Pilgram

benedikt.pilgram@student.unibe.ch


## Acknowledgments
...

## Key References

## License
- **Code:** MIT License
- **Documentation:** CC-BY 4.0

---

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![R Version](https://img.shields.io/badge/R-%3E%3D%204.3.0-blue.svg)](https://www.r-project.org/)
