# Architektur-Übersicht: Stadtratssitzungs ETL-Pipeline

## System-Architektur

```
┌─────────────────────────────────────────────────────────────────────┐
│                          INPUT: HTML DUMPS                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ sitzung1.html│  │ sitzung2.html│  │ sitzung3.html│  ...          │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EXTRACTION (BeautifulSoup)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  HTMLExtractor                                               │   │
│  │  • Parse HTML-Struktur                                       │   │
│  │  • Extrahiere: Meetings, Agenda Items, Papers, Documents     │   │
│  │  • Pattern Matching für Datum, Ort, Gremium                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   TRANSFORMATION (spaCy + Geopy)                    │
│  ┌───────────────────────┐    ┌──────────────────────────────────┐  │
│  │  NER (spaCy)          │    │  Geocoding (Nominatim)           │  │
│  │  • Personen           │    │  • Adresse → Koordinaten         │  │
│  │  • Organisationen     │    │  • Rate Limiting                 │  │
│  │  • Orte               │    │  • Cache                         │  │
│  │  • Datumsangaben      │    │  • PostGIS Point                 │  │
│  │  • Geldbeträge        │    └──────────────────────────────────┘  │
│  └───────────────────────┘                                          │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  DataTransformer                                             │   │
│  │  • Datenbereinigung                                          │   │
│  │  • Validierung                                               │   │
│  │  • Anreicherung mit Metadaten                                │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│                LOADING (PostgreSQL + PostGIS)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  DatabaseLoader                                              │   │
│  │  • Batch Inserts                                             │   │
│  │  • UPSERT (ON CONFLICT)                                      │   │
│  │  • Transaction Management                                    │   │
│  │  • Referenzielle Integrität                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│              PostgreSQL/PostGIS DATABASE                            │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  meetings    │  │ agenda_items │  │   papers     │               │
│  │              │  │              │  │              │               │
│  │ • id         │  │ • id         │  │ • id         │               │
│  │ • name       │  │ • meeting_id │  │ • reference  │               │
│  │ • start_time │  │ • title      │  │ • name       │               │
│  │ • location   │  │ • position   │  │ • full_text  │               │
│  │ • geometry   │  │ • result     │  │ • locations  │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ organizations│  │   persons    │  │  documents   │               │
│  └──────────────┘  └──────────────┘  └──────────────┘               │
│                                                                     │
│  Features:                                                          │
│  ✓ Full-Text Search (tsvector)                                      │
│  ✓ Spatial Queries (PostGIS)                                        │
│  ✓ Trigram Similarity                                               │
│  ✓ Generated Columns                                                │
│  ✓ Views & Functions                                                │
└─────────────────────────────────────────────────────────────────────┘
```

## Datenfluss

```
HTML → Parse → Extract Entities → Geocode → Validate → Insert DB → Index
  ↓      ↓           ↓              ↓          ↓          ↓         ↓
 Log   Error      spaCy         Nominatim   Quality    UPSERT   Search
              Handling                       Checks
```

## Datenbankschema: Relationen

```
organizations (Gremien)
    ↑
    │ 1:n
    │
meetings (Sitzungen)
    ↑                    ↑
    │ 1:n                │ n:m
    │                    │
agenda_items         meeting_documents
    ↑                    ↓
    │ n:m            documents (PDFs)
    │                    ↓
paper_agenda_items      n:m
    ↓                    ↓
papers (Vorlagen)    paper_documents
    ↓
    n:1
    ↓
organizations/persons (Urheber)
```

## Technologie-Stack

| Layer | Technologie | Zweck |
|-------|-------------|-------|
| **Extraction** | BeautifulSoup, lxml | HTML Parsing |
| **NLP** | spaCy (de_core_news_lg) | Named Entity Recognition |
| **Geocoding** | geopy, Nominatim | Adress → Koordinaten |
| **Database** | PostgreSQL 14+, PostGIS 3.x | Datenspeicherung |
| **ORM** | SQLAlchemy, GeoAlchemy2 | Datenbank-Abstraktion |
| **Workflow** | Python 3.9+ | Orchestrierung |

## Datenqualitäts-Pipeline

```
1. EXTRACTION
   ├─→ HTML valid?
   ├─→ Required fields present?
   └─→ Log to scraping_log

2. TRANSFORMATION
   ├─→ Date parsing successful?
   ├─→ NER entities plausible?
   ├─→ Geocoding success rate?
   └─→ Log to data_quality_issues

3. LOADING
   ├─→ Unique constraints violated?
   ├─→ Foreign keys valid?
   ├─→ Geometries valid?
   └─→ Rollback on error

4. VALIDATION
   ├─→ Completeness checks
   ├─→ Consistency checks
   └─→ Business rule validation
```

## Performance-Optimierung

### Indizes

- **Full-Text**: GIN-Index auf search_vector
- **Spatial**: GIST-Index auf Geometrien
- **Foreign Keys**: B-Tree-Index
- **Trigram**: GIN-Index auf Namen/Texte

### Caching

- Geocoding-Cache (LRU, 1000 Einträge)
- HTML-Parser-Resulte
- NER-Modell in Memory

### Batch Processing

- Bulk Inserts (100 Records/Batch)
- Connection Pooling
- Prepared Statements

## Query-Patterns

### 1. Volltext-Suche
```sql
SELECT * FROM papers
WHERE search_vector @@ to_tsquery('german', 'Bebauungsplan & Wohngebiet');
```

### 2. Räumliche Abfrage
```sql
SELECT * FROM meetings
WHERE ST_DWithin(
    location_geometry,
    ST_Point(7.4474, 46.9480),
    1000  -- Meter
);
```

### 3. Zeitreihen-Analyse
```sql
SELECT
    date_trunc('month', start_time) as month,
    COUNT(*) as meeting_count
FROM meetings
GROUP BY month
ORDER BY month;
```

## Monitoring & Alerting

```
Metrics:
├─ Processing Time
├─ Success/Error Rate
├─ Geocoding Success Rate
├─ Database Size
├─ Query Performance
└─ Data Quality Score

Alerts:
├─ Processing > 5min
├─ Error Rate > 10%
├─ Disk Space < 20%
└─ Data Quality < 80%
```

## Skalierbarkeit

### Horizontal Scaling
- PostgreSQL Replication
- Read Replicas für Queries
- Sharding nach Zeitraum/Organisation

### Vertical Scaling
- Mehr RAM für PostGIS
- SSD für Indizes
- CPU für NER-Processing

### Optimization Strategies
- Incremental Processing
- Parallel HTML Parsing
- Async Geocoding
- Connection Pooling
