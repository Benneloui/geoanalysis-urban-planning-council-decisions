# Project Proposal: Spatial-Temporal Analysis of Municipa Councilmeeting documents

Proseminar - Applied Geodata Science

University of Bern

**Author:** Benedikt Pilgram

**Supervisor:** Prof. Benjamin Stocker

## Summary

This project investigates the spatial and temporal patterns of municipal council decisions in a selected German city X. Using council meeting information from OParl APIs, combined with geodata, it analyze where and when decisions occur over a time period. The reproducible R-based workflow can be transferred to other municipalities, contributing methodologically to the intersection of e-government data and spatial planning research.

## Background and Motivation

Urban planning is a core function of local government, directly affecting citizens' built environment and housing availability. Municipal councils (Gemeinderat, Stadtrat) play a critical decision-making role in adopting, modifying, or rejecting plans. However, the spatial and temporal patterns of these political decisions remain largely intrasperent. But efforts to change this have been made to some extent.

- Municipal council decisions are increasingly digitized and accessible through standards like OParl (Germany) or similar e-government initiatives
- Development plans become more documented with new standards in municipal geoportals

But critical gaps remain:

- **No comprehensive spatial analysis** of where council planning decisions concentrate within cities
- **Limited understanding** of temporal dynamics in planning activity (trends, acceleration, seasonal patterns)
- **Unclear relationship** between designated urban renewal areas and actual political prioritization
- **Absence of reproducible methods** for analyzing council information spatially

Germany's recent "Bauturbo" policies aim to accelerate development approvals, but their effectiveness may depend on underlying patterns of political attention and administrative capacity. Understanding where and when councils already focus planning efforts provides baseline evidence for evaluating policy impacts. Additionally, the methodology addresses the growing availability of structured municipal data (e-government platforms), demonstrating how open data can inform urban research.

## Objective

**Research Quesiton:**
> "Where and when is geographically relevant information, in City "Augsburg", negotiated politically? What anomalies does a spatial-temporal analysis of City Council information reveal?"


## Implementation

#### Data Sources - Dataset 1: Council Meeting Information

**Primary Option - [OPARL](https://github.com/OParl) API:**
- **Description:** Standardized API for accessing German municipal council information
- **Format:** JSON (structured data)
- **Access:** Public APIs from municipalities implementing OParl standard
- **Variables:** Meeting date, agenda items, titles, full text, decision outcomes, attachments
- **License:** Typically Open Data (varies by municipality)

```
┌─────────────────────────────────────────────────────────┐
│               Municipal Council System                  │
│  (What the municipality uses internally)                │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────────────────────────────────┐           │
│  │  Ratsinformationssystem (RIS)            │           │
│  │  ──────────────────────────              │           │
│  │  Commercial products like:               │           │
│  │  - SessionNet (Somacos)                  │           │
│  │  - Allris (cc|gis)                       │           │
│  │  - eSitzung (STERNBERG)                  │           │
│  │  - Vois (Webforum)                       │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                   │
│         stores data in ↓                                │
│                                                         │
│  ┌──────────────────────────────────────────┐           │
│  │         Database (Backend)               │           │
│  │  ────────────────────────                │           │
│  │  Usually:                                │           │
│  │  • SQL Server (Microsoft)                │           │
│  │  • Oracle Database                       │           │
│  │  • PostgreSQL                            │           │
│  │  • MySQL/MariaDB                         │           │
│  │                                          │           │
│  │  Tables for:                             │           │
│  │  - Meetings (Sitzungen)                  │           │
│  │  - Agenda items (Tagesordnungspunkte)    │           │
│  │  - Papers (Drucksachen)                  │           │
│  │  - Persons (Personen)                    │           │
│  │  - Organizations (Gremien)               │           │
│  │  - Files (Dokumente)                     │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                   │
│         provides    ↓                                   │
│                                                         │
│  ┌──────────────────────────────────────────┐           │
│  │      OParl API Server                    │           │
│  │  ────────────────────────                │           │
│  │  REST API that:                          │           │
│  │  1. Queries the database                 │           │
│  │  2. Formats results as JSON              │           │
│  │  3. Handles pagination                   │           │
│  │  4. Manages authentication (if needed)   │           │
│  └──────────────────┬───────────────────────┘           │
│                     │                                   │
└─────────────────────┼───────────────────────────────────┘
                      │
                      │ HTTP/HTTPS
                      │ (Public Internet)
                      ↓
          ┌─────────────────────────┐
          │     R Code              │
          │  ──────────────         │
          │  library(httr)          │
          │  GET("/oparl/meeting")  │
          └─────────────────────────┘
```


**Socioeconomic indicators (optional):**
- Source: Census data, statistical yearbooks
- Variables: Population density, income, demographics


1. **Connecting to OParl API:** Successfully retrieves council meeting data from Augsburg's public OParl endpoint
2. **Geocoding locations:** Converts district names etc. to coordinates for spatial analysis
3. **Creating visualizations:**

---


## Risks and Contingency in this Project

### Risk 1: Georeferencing Fails

**Risk Description:**
- Cannot reliably extract location information from text
- Geocoding accuracy too low
- Spatial join unsuccessful

**Probability:** Medium
**Impact:** High

**Mitigation Strategies:**
1. **Early testing:** Test georeferencing on sample
2. **Multiple methods:**
   - Direct address extraction + geocoding
   - Plan name matching with B-Plan registry
   - District name extraction (coarser but more reliable)
3. **Manual validation:** Hand-check ambiguous cases
4. **Accept partial success:** 70-80% georeferenced may be sufficient

### Risk 2: No Significant Spatial Patterns

**Risk Description:**
- Data too sparse for meaningful spatial analysis

**Probability:** Low (there's almost always some pattern)
**Impact:** Medium

**Mitigation Strategies:**
1. **Framing:** "No clustering" is itself an interesting finding
   - Contradicts expectations from literature
   - Suggests random/equity-driven allocation
   - Worthy of discussion

### Risk 3: Time Constraints

**Risk Description:**
- Data collection takes longer than expected
- Technical difficulties slow analysis
- Writing takes more time than planned

**Probability:** High (common in research)
**Impact:** Medium

---

*Bibliography will be completed during literature review phase (Weeks 1-2).*

## Contact Information

Name: Benedikt Pilgram

Email: benedikt.pilgram@student.unibe.ch


---

*This proposal is a living document. It will be updated as the project evolves, with all changes tracked in the GitHub repository.*
