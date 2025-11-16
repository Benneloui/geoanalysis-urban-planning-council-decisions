# SQL Query Cheat Sheet - Stadtratssitzungs DB

## Basis-Queries

### 1. Alle Meetings anzeigen
```sql
SELECT 
    id,
    name,
    start_time,
    location,
    meeting_status
FROM meetings
ORDER BY start_time DESC
LIMIT 20;
```

### 2. Meetings mit Agenda Items Count
```sql
SELECT 
    m.name,
    m.start_time,
    COUNT(ai.id) as agenda_items_count
FROM meetings m
LEFT JOIN agenda_items ai ON ai.meeting_id = m.id
GROUP BY m.id
ORDER BY m.start_time DESC;
```

### 3. Tagesordnungspunkte einer Sitzung
```sql
SELECT 
    number,
    title,
    result,
    voting_yes,
    voting_no
FROM agenda_items
WHERE meeting_id = 'YOUR-UUID-HERE'
ORDER BY position;
```

## Volltext-Suche

### 4. Suche nach "Bebauungsplan"
```sql
-- Einfache Suche
SELECT 
    name,
    date_published,
    ts_rank(search_vector, query) as relevance
FROM papers, 
     to_tsquery('german', 'Bebauungsplan') query
WHERE search_vector @@ query
ORDER BY relevance DESC;

-- Mit UND-Verknüpfung
SELECT * FROM papers
WHERE search_vector @@ to_tsquery('german', 'Bebauungsplan & Wohngebiet');

-- Mit ODER-Verknüpfung
SELECT * FROM papers
WHERE search_vector @@ to_tsquery('german', 'Bebauungsplan | Flächennutzung');

-- Mit Negation
SELECT * FROM papers
WHERE search_vector @@ to_tsquery('german', 'Bebauungsplan & !Gewerbe');
```

### 5. Ähnlichkeitssuche (Fuzzy)
```sql
-- Trigram-Ähnlichkeit
SELECT 
    name,
    similarity(name, 'Bebauungspln') as sim
FROM papers
WHERE name % 'Bebauungspln'  -- % ist Similarity-Operator
ORDER BY sim DESC;
```

## Räumliche Queries (PostGIS)

### 6. Meetings in der Nähe eines Punktes
```sql
-- Meetings im 1km Radius
SELECT 
    name,
    location,
    ST_Distance(
        location_geometry,
        ST_SetSRID(ST_Point(7.4474, 46.9480), 4326)::geography
    ) as distance_meters
FROM meetings
WHERE location_geometry IS NOT NULL
  AND ST_DWithin(
      location_geometry::geography,
      ST_SetSRID(ST_Point(7.4474, 46.9480), 4326)::geography,
      1000  -- Meter
  )
ORDER BY distance_meters;
```

### 7. Meetings in Bounding Box
```sql
-- Alle Meetings im Stadtgebiet
SELECT 
    name,
    location,
    ST_X(location_geometry) as lon,
    ST_Y(location_geometry) as lat
FROM meetings
WHERE ST_Contains(
    ST_MakeEnvelope(7.40, 46.90, 7.50, 47.00, 4326),
    location_geometry
);
```

### 8. Nächstgelegenes Meeting zu einem Punkt
```sql
SELECT 
    name,
    location,
    ST_Distance(
        location_geometry::geography,
        ST_SetSRID(ST_Point(7.4474, 46.9480), 4326)::geography
    ) as distance_meters
FROM meetings
WHERE location_geometry IS NOT NULL
ORDER BY location_geometry <-> ST_SetSRID(ST_Point(7.4474, 46.9480), 4326)
LIMIT 1;
```

## Zeitreihen & Statistiken

### 9. Meetings pro Monat
```sql
SELECT 
    date_trunc('month', start_time) as month,
    COUNT(*) as meeting_count,
    COUNT(DISTINCT organization_id) as organizations_active
FROM meetings
WHERE start_time >= NOW() - INTERVAL '1 year'
GROUP BY month
ORDER BY month;
```

### 10. Top Themen (häufigste Schlagworte in Agenda Items)
```sql
SELECT 
    word,
    COUNT(*) as frequency
FROM (
    SELECT unnest(string_to_array(lower(title), ' ')) as word
    FROM agenda_items
) words
WHERE length(word) > 5  -- Nur längere Wörter
GROUP BY word
ORDER BY frequency DESC
LIMIT 20;
```

### 11. Abstimmungsverhalten
```sql
-- Angenommene vs. abgelehnte Anträge
SELECT 
    result,
    COUNT(*) as count,
    ROUND(AVG(voting_yes), 2) as avg_yes_votes,
    ROUND(AVG(voting_no), 2) as avg_no_votes
FROM agenda_items
WHERE result IS NOT NULL
GROUP BY result
ORDER BY count DESC;
```

## Verknüpfte Abfragen

### 12. Papers mit ihren Dokumenten
```sql
SELECT 
    p.reference,
    p.name,
    p.date_published,
    json_agg(json_build_object(
        'filename', d.filename,
        'type', d.document_type,
        'size_mb', ROUND(d.file_size_bytes / 1024.0 / 1024.0, 2)
    )) as documents
FROM papers p
LEFT JOIN paper_documents pd ON pd.paper_id = p.id
LEFT JOIN documents d ON d.id = pd.document_id
GROUP BY p.id
ORDER BY p.date_published DESC;
```

### 13. Gremien-Aktivität
```sql
SELECT 
    o.name as organization,
    o.organization_type,
    COUNT(DISTINCT m.id) as meetings_count,
    COUNT(DISTINCT ai.id) as agenda_items_count,
    MIN(m.start_time) as first_meeting,
    MAX(m.start_time) as last_meeting
FROM organizations o
LEFT JOIN meetings m ON m.organization_id = o.id
LEFT JOIN agenda_items ai ON ai.meeting_id = m.id
WHERE m.start_time >= NOW() - INTERVAL '1 year'
GROUP BY o.id
ORDER BY meetings_count DESC;
```

### 14. Person mit ihren Mitgliedschaften
```sql
SELECT 
    p.given_name || ' ' || p.family_name as full_name,
    p.academic_title,
    json_agg(json_build_object(
        'organization', o.name,
        'role', m.role,
        'since', m.start_date,
        'until', m.end_date
    )) as memberships
FROM persons p
LEFT JOIN memberships m ON m.person_id = p.id
LEFT JOIN organizations o ON o.id = m.organization_id
WHERE p.status = 'active'
GROUP BY p.id;
```

## Data Quality Queries

### 15. Meetings ohne Geocoding
```sql
SELECT 
    name,
    location,
    scraped_at
FROM meetings
WHERE location IS NOT NULL
  AND location_geometry IS NULL
ORDER BY scraped_at DESC;
```

### 16. Papers ohne Text
```sql
SELECT 
    reference,
    name,
    paper_type
FROM papers
WHERE (full_text IS NULL OR full_text = '')
  AND (abstract IS NULL OR abstract = '')
ORDER BY date_published DESC;
```

### 17. Geocoding Success Rate
```sql
SELECT 
    COUNT(*) as total_meetings,
    COUNT(location_geometry) as geocoded,
    ROUND(
        COUNT(location_geometry)::numeric / COUNT(*)::numeric * 100, 
        2
    ) as success_rate_percent
FROM meetings
WHERE location IS NOT NULL;
```

### 18. Data Quality Issues Overview
```sql
SELECT 
    table_name,
    issue_type,
    severity,
    COUNT(*) as issue_count,
    COUNT(*) FILTER (WHERE status = 'open') as open_issues
FROM data_quality_issues
GROUP BY table_name, issue_type, severity
ORDER BY issue_count DESC;
```

## Export Queries

### 19. Export als CSV
```sql
\copy (
    SELECT 
        m.name,
        m.start_time,
        m.location,
        o.name as organization
    FROM meetings m
    LEFT JOIN organizations o ON o.id = m.organization_id
    WHERE m.start_time >= '2024-01-01'
    ORDER BY m.start_time
) TO '/tmp/meetings_2024.csv' CSV HEADER;
```

### 20. Export als GeoJSON
```sql
SELECT json_build_object(
    'type', 'FeatureCollection',
    'features', json_agg(ST_AsGeoJSON(t.*)::json)
)
FROM (
    SELECT 
        name,
        location,
        location_geometry
    FROM meetings
    WHERE location_geometry IS NOT NULL
) AS t;
```

## Maintenance Queries

### 21. Vacuuming & Analysis
```sql
-- Statistiken aktualisieren
ANALYZE meetings;
ANALYZE agenda_items;
ANALYZE papers;

-- Speicher freigeben
VACUUM ANALYZE;
```

### 22. Index-Status prüfen
```sql
SELECT 
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size
FROM pg_indexes
JOIN pg_class ON pg_indexes.indexname = pg_class.relname
WHERE schemaname = 'public'
ORDER BY pg_relation_size(indexrelid) DESC;
```

### 23. Datenbank-Größe
```sql
SELECT 
    pg_size_pretty(pg_database_size('stadtrat_db')) as database_size,
    pg_size_pretty(pg_total_relation_size('meetings')) as meetings_size,
    pg_size_pretty(pg_total_relation_size('papers')) as papers_size,
    pg_size_pretty(pg_total_relation_size('documents')) as documents_size;
```

## Performance Tuning

### 24. Slow Query Analysis
```sql
-- Aktiviere Query Stats (als Superuser)
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
ALTER SYSTEM SET pg_stat_statements.track = all;
-- Neustart erforderlich

-- Top 10 langsamste Queries
SELECT 
    query,
    calls,
    total_exec_time,
    mean_exec_time,
    max_exec_time
FROM pg_stat_statements
ORDER BY total_exec_time DESC
LIMIT 10;
```

### 25. Explain Plan
```sql
EXPLAIN ANALYZE
SELECT * FROM meetings
WHERE start_time >= NOW() - INTERVAL '1 year'
  AND location_geometry IS NOT NULL;
```

## Advanced: Window Functions

### 26. Running Total von Meetings
```sql
SELECT 
    date_trunc('month', start_time) as month,
    COUNT(*) as meetings_this_month,
    SUM(COUNT(*)) OVER (ORDER BY date_trunc('month', start_time)) as cumulative_total
FROM meetings
GROUP BY month
ORDER BY month;
```

### 27. Rank von Themen nach Häufigkeit
```sql
WITH topic_counts AS (
    SELECT 
        title,
        COUNT(*) as frequency
    FROM agenda_items
    WHERE title ILIKE '%Bebauungsplan%'
    GROUP BY title
)
SELECT 
    title,
    frequency,
    RANK() OVER (ORDER BY frequency DESC) as rank
FROM topic_counts;
```

---

**Tipp**: Für interaktive Exploration nutze `psql` mit:
```bash
psql -d stadtrat_db -c "SELECT * FROM v_meetings_full LIMIT 5;"
```
