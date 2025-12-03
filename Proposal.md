# Project Proposal: Spatial Analysis of Municipal Council Documents

**Case Study: City of Augsburg**

Proseminar - Applied Geodata Science | University of Bern

Author: Benedikt Pilgram

Supervisor: Prof. Benjamin Stocker

## Summary

This project investigates municipal council decisions in **Augsburg, Germany**. By leveraging the **OParl API** interface, unstructured parliamentary documents (session data and papers) are transformed into structured datasets. The project applies a **hybrid extraction pipeline** combining Named Entity Recognition (NER), Fuzzy Matching, and OpenStreetMap validation to geolocate political activities. The analysis aims to reveal patterns of the council and spatial distributions of political attention (e.g., center vs. periphery bias).

## Background and Motivation

Urban planning is a core function of local government, yet the patterns of these decisions often remain hidden in thousands of PDF documents. While digitization standards like **OParl** exist, they are rarely used for quantitative spatial analysis.


## Objectives & Research Questions

**Primary Research Question:**

> "How is political attention distributed spatially across the districts of Augsburg, and what temporal patterns define the council's workflow?"

**Sub-questions:**

1. **Temporal:** When does the council meet? Are there significant shifts in meeting frequencies or times over the legislative period (2020–2025)?

2. **Spatial:** How is political attention (measured by parliamentary activity) distributed spatially across the districts of Augsburg, and does a center-periphery bias exist?


## Methodology & Implementation

The project moves beyond simple keyword searching by implementing a **Python-based ETL pipeline** (Extract, Transform, Load).

#### 1. Data

- **Source:** Official OParl API of the City of Augsburg (SessionNet).


#### 2. The "Location Extractor"

To solve the problem of unstructured location data in titles (e.g., _"Sanierung der Maxstr."_), a three-stage extraction logic is developed:

1. **NER (Named Entity Recognition):** Using `spaCy` (model: `de_core_news_sm`) to identify location entities in text context.

2. **Ground Truth Validation:** Extracted tokens are matched against a local **OpenStreetMap (OSM) dataset** containing all validated street names in Augsburg (via Overpass API).

3. **Fuzzy Matching:** Using Levenshtein distance (`thefuzz`) to map typos or abbreviations in documents to the correct OSM street name before geocoding.

## Preliminary Results (Proof of Concept)

A pilot run of the data pipeline has validated the feasibility:

- **Data Base:** Successfully harvested **~750 meetings** from Jan 2020 to Nov 2025.

- **Geocoding Success:** The streetnames form the meta Date got successfully geocoded to coordinates.


## Challenges
- Augsburg uses NON-STANDARD OParl endpoint names
- need to analyse the Augsburg OParl Standart first

## Tools & Stack

- **Language:** Mainly Python (VS Code Environment)

- **Data Fetching:** `requests` (with Retry-Adapter)

- **NLP & Matching:** `spaCy`, `thefuzz`

- **Geodata:** `geopy` (Nominatim), `Overpass API` (OSM)

- **Analysis/Viz:** `pandas`, `matplotlib`, `folium`


## Contact Information

Name: Benedikt Pilgram

Email: benedikt.pilgram@student.unibe.ch
