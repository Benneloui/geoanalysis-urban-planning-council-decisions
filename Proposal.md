# Project Proposal: Spatial-Temporal Analysis of Council Decisions on Development Plans

Proseminar - Applied Geodata Science

University of Bern

**Author:** Benedikt Pilgram

**Supervisor:** Prof. Benjamin Stocker

## 1. Summary

This project investigates the spatial and temporal patterns of municipal council decisions related to development plans (Bebauungspläne) in a selected German or Swiss city. Using council meeting information from either OParl APIs or manual collection, combined with development plan geodata, I analyze where and when planning decisions occur over a time period. The reproducible R-based workflow can be transferred to other municipalities, contributing methodologically to the intersection of e-government data and spatial planning research.

## 2. Background and Motivation

Urban development planning is a core function of local government, directly affecting citizens' built environment, housing availability, and neighborhood development. Municipal councils (Gemeinderat, Stadtrat) play a critical decision-making role in adopting, modifying, or rejecting development plans (Bebauungspläne). However, the spatial and temporal patterns of these political decisions remain largely intrasperent, despite their importance for understanding:

- **Planning priorities:** Which districts receive political attention and resources?
- **Urban renewal effectiveness:** Do designated renewal areas receive proportionally more planning activity?
- **Democratic representation:** Are all neighborhoods equally represented in planning decisions?
- **Policy implementation:** How do political timelines align with planning goals?


Existing research has established that:

- Municipal council decisions are increasingly digitized and accessible through standards like OParl (Germany) or similar e-government initiatives
- Development plans are well-documented in municipal geoportals
- Urban planning processes involve spatial inequalities


Despite this foundation, critical gaps remain:

- **No comprehensive spatial analysis** of where council planning decisions concentrate within cities
- **Limited understanding** of temporal dynamics in planning activity (trends, acceleration, seasonal patterns)
- **Unclear relationship** between designated urban renewal areas and actual political prioritization
- **Absence of reproducible methods** for analyzing council information spatially


Germany's recent "Bauturbo" policies aim to accelerate development approvals, but their effectiveness may depend on underlying patterns of political attention and administrative capacity. Understanding where and when councils already focus planning efforts provides baseline evidence for evaluating policy impacts. Additionally, the methodology addresses the growing availability of structured municipal data (e-government platforms), demonstrating how open data can inform urban research.

## 3. Objective


**Research Quesiton:**
> "Where and when is geographically relevant information, such as development plans in City X, negotiated politically? What anomalies does a spatial-temporal analysis of City Council information in period Y reveal? How does the ratio of decisions in planned and unplanned areas vary?"


This descriptive-exploratory question investigates:
1. **Spatial concentration:** In which districts do development plan decisions cluster?
2. **Temporal patterns:** Has planning activity increased, decreased, or remained stable? Are there seasonal variations?
3. **Thematic focus:** What types of plans dominate (residential, commercial, green space)?
4. **Process characteristics:** How long do planning processes take from initial discussion to final decision?

## 4. Implementation

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
          │    Your R Code          │
          │  ──────────────         │
          │  library(httr)          │
          │  GET("/oparl/meeting")  │
          └─────────────────────────┘
```


**Fallback Option - Manual Collection:**
- **Description:** Direct download from municipal council information portals
- **Format:** PDF/HTML documents
- **Access:** Municipal websites (e.g., Ratsinformationssystem)
- **Process:** Search for "Bebauungsplan", download relevant documents
- **Documentation:** Collection protocol will be documented


**Socioeconomic indicators (optional):**
- Source: Census data, statistical yearbooks
- Variables: Population density, income, demographics

## 5. Proof-of-Concept Demo

**Demo Implementation:** A working proof-of-concept demonstration has been created using the city of Augsburg as a test case. The demo (`tests_demo/demo_oparl_augsburg.R`) validates the technical feasibility of the project by:

1. **Connecting to OParl API:** Successfully retrieves council meeting data from Augsburg's public OParl endpoint
2. **Extracting Bebauungsplan references:** Uses text mining to identify development plan discussions in agenda items
3. **Geocoding locations:** Converts district names to coordinates for spatial analysis
4. **Creating visualizations:** Generates three types of plots:
   - Temporal distribution (when decisions occur)
   - District frequency (where decisions cluster)
   - Spatial map (geographic patterns)

**Key Findings from Demo:**
- OParl API provides structured, machine-readable council data
- Development plan references can be automatically detected using text patterns
- Spatial analysis is feasible with district-level geocoding
- The methodology is reproducible and transferable to other cities

**Modular Architecture:** The demo leverages 39 reusable functions organized in `/R/` directory, making the workflow adaptable to Augsburg (primary study city) and other municipalities implementing OParl.

**Demo outputs:** All visualizations are saved with `demo_augsburg_*` prefix to distinguish them from production analysis results.

---

## 6. Timeline

#### Step 1: Data Collection & Preprocessing (Weeks 1-2)

#### Step 2: Georeferencing (Weeks 2-3)

#### Step 3: Analysis (Weeks 3-5)

#### Step 5: Visualization & Reporting (Weeks 5-6)


## 7. Risks and Contingency

### Risk 1: Georeferencing Fails

**Risk Description:**
- Cannot reliably extract location information from text
- Geocoding accuracy too low
- Spatial join with development plans unsuccessful

**Probability:** Medium
**Impact:** High

**Mitigation Strategies:**
1. **Early testing:** Test georeferencing on 20-document sample (Week 3)
2. **Multiple methods:**
   - Direct address extraction + geocoding
   - Plan name matching with B-Plan registry
   - District name extraction (coarser but more reliable)
3. **Manual validation:** Hand-check ambiguous cases
4. **Accept partial success:** 70-80% georeferenced may be sufficient

**Adaptive Strategy:**
- Week 4 checkpoint: Assess georeferencing success rate


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

**Mitigation Strategies:**
1. **Start immediately:** Begin data collection in Week 1, parallel with proposal
2. **Buffer time:** Build 1-week buffer before final deadline

---


*Bibliography will be completed during literature review phase (Weeks 1-2).*



## Contact Information

Name: Benedikt Pilgram

Email: benedikt.pilgram@student.unibe.ch


---

*This proposal is a living document. It will be updated as the project evolves, with all changes tracked in the GitHub repository.*
