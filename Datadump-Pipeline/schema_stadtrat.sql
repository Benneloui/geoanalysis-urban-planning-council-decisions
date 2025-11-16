-- ============================================
-- PostgreSQL Schema für Ratsinformationssystem
-- HTML-Dump Import
-- ============================================

-- Datenbank erstellen (falls noch nicht vorhanden)
CREATE DATABASE stadtrat_db
    ENCODING 'UTF8'
    LC_COLLATE 'de_DE.UTF-8'
    LC_CTYPE 'de_DE.UTF-8';

\c stadtrat_db

-- Extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Trigger Function für auto-update von modified_at
CREATE OR REPLACE FUNCTION update_modified_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.modified_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- CORE TABLES
-- ============================================

-- Organizations
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    short_name VARCHAR(50),
    organization_type VARCHAR(50),
    description TEXT,
    founding_date DATE,
    dissolution_date DATE,
    parent_organization_id UUID REFERENCES organizations(id),
    website VARCHAR(500),
    email VARCHAR(255),
    phone VARCHAR(50),
    source_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(description, '')), 'B')
    ) STORED
);

CREATE INDEX idx_organizations_type ON organizations(organization_type);
CREATE INDEX idx_organizations_parent ON organizations(parent_organization_id);
CREATE INDEX idx_organizations_search ON organizations USING GIN(search_vector);

CREATE TRIGGER update_organizations_modtime
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Persons
CREATE TABLE persons (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    given_name VARCHAR(100),
    family_name VARCHAR(100) NOT NULL,
    academic_title VARCHAR(50),
    form_of_address VARCHAR(20),
    email VARCHAR(255),
    phone VARCHAR(50),
    status VARCHAR(20) DEFAULT 'active',
    source_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(given_name, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(family_name, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(academic_title, '')), 'B')
    ) STORED
);

CREATE INDEX idx_persons_family_name ON persons(family_name);
CREATE INDEX idx_persons_status ON persons(status);
CREATE INDEX idx_persons_search ON persons USING GIN(search_vector);

CREATE TRIGGER update_persons_modtime
    BEFORE UPDATE ON persons
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Memberships
CREATE TABLE memberships (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    person_id UUID NOT NULL REFERENCES persons(id) ON DELETE CASCADE,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    role VARCHAR(100),
    start_date DATE,
    end_date DATE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_membership UNIQUE(person_id, organization_id, start_date)
);

CREATE INDEX idx_memberships_person ON memberships(person_id);
CREATE INDEX idx_memberships_organization ON memberships(organization_id);
CREATE INDEX idx_memberships_dates ON memberships(start_date, end_date);

-- Meetings
CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    organization_id UUID REFERENCES organizations(id),
    meeting_type VARCHAR(50),
    start_time TIMESTAMP WITH TIME ZONE,
    end_time TIMESTAMP WITH TIME ZONE,
    location VARCHAR(255),
    location_geometry GEOMETRY(Point, 4326),
    meeting_status VARCHAR(20) DEFAULT 'scheduled',
    participants JSONB,
    invitation_date DATE,
    source_url TEXT,
    source_html_path TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(location, '')), 'B')
    ) STORED
);

CREATE INDEX idx_meetings_organization ON meetings(organization_id);
CREATE INDEX idx_meetings_start_time ON meetings(start_time);
CREATE INDEX idx_meetings_status ON meetings(meeting_status);
CREATE INDEX idx_meetings_location_geom ON meetings USING GIST(location_geometry);
CREATE INDEX idx_meetings_search ON meetings USING GIN(search_vector);

CREATE TRIGGER update_meetings_modtime
    BEFORE UPDATE ON meetings
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Agenda Items
CREATE TABLE agenda_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    number VARCHAR(20),
    title TEXT NOT NULL,
    description TEXT,
    parent_item_id UUID REFERENCES agenda_items(id),
    position INTEGER,
    result VARCHAR(100),
    result_details TEXT,
    voting_yes INTEGER,
    voting_no INTEGER,
    voting_abstention INTEGER,
    voting_absent INTEGER,
    source_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(description, '')), 'B') ||
        setweight(to_tsvector('german', coalesce(result_details, '')), 'C')
    ) STORED
);

CREATE INDEX idx_agenda_items_meeting ON agenda_items(meeting_id);
CREATE INDEX idx_agenda_items_parent ON agenda_items(parent_item_id);
CREATE INDEX idx_agenda_items_position ON agenda_items(meeting_id, position);
CREATE INDEX idx_agenda_items_search ON agenda_items USING GIN(search_vector);

CREATE TRIGGER update_agenda_items_modtime
    BEFORE UPDATE ON agenda_items
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Papers
CREATE TABLE papers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    reference VARCHAR(100) UNIQUE,
    name VARCHAR(500) NOT NULL,
    paper_type VARCHAR(50),
    abstract TEXT,
    full_text TEXT,
    date_published DATE,
    date_due DATE,
    originator_organization_id UUID REFERENCES organizations(id),
    originator_person_id UUID REFERENCES persons(id),
    mentioned_locations TEXT[],
    location_geometry GEOMETRY(MultiPoint, 4326),
    source_url TEXT,
    source_html_path TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(name, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(abstract, '')), 'B') ||
        setweight(to_tsvector('german', coalesce(full_text, '')), 'C')
    ) STORED
);

CREATE INDEX idx_papers_reference ON papers(reference);
CREATE INDEX idx_papers_type ON papers(paper_type);
CREATE INDEX idx_papers_date_published ON papers(date_published);
CREATE INDEX idx_papers_originator_org ON papers(originator_organization_id);
CREATE INDEX idx_papers_location_geom ON papers USING GIST(location_geometry);
CREATE INDEX idx_papers_search ON papers USING GIN(search_vector);
CREATE INDEX idx_papers_locations ON papers USING GIN(mentioned_locations);

CREATE TRIGGER update_papers_modtime
    BEFORE UPDATE ON papers
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- Documents
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(500) NOT NULL,
    title VARCHAR(500),
    mime_type VARCHAR(100),
    file_size_bytes BIGINT,
    file_path TEXT,
    extracted_text TEXT,
    page_count INTEGER,
    document_date DATE,
    document_type VARCHAR(50),
    extracted_addresses JSONB,
    extracted_persons JSONB,
    extracted_organizations JSONB,
    extracted_dates JSONB,
    extracted_amounts JSONB,
    source_url TEXT,
    download_url TEXT,
    scraped_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    modified_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    search_vector tsvector GENERATED ALWAYS AS (
        setweight(to_tsvector('german', coalesce(title, '')), 'A') ||
        setweight(to_tsvector('german', coalesce(extracted_text, '')), 'C')
    ) STORED
);

CREATE INDEX idx_documents_mime_type ON documents(mime_type);
CREATE INDEX idx_documents_type ON documents(document_type);
CREATE INDEX idx_documents_date ON documents(document_date);
CREATE INDEX idx_documents_search ON documents USING GIN(search_vector);
CREATE INDEX idx_documents_extracted ON documents USING GIN(extracted_addresses);

CREATE TRIGGER update_documents_modtime
    BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_modified_column();

-- ============================================
-- JUNCTION TABLES
-- ============================================

CREATE TABLE paper_agenda_items (
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    agenda_item_id UUID NOT NULL REFERENCES agenda_items(id) ON DELETE CASCADE,
    role VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (paper_id, agenda_item_id)
);

CREATE INDEX idx_paper_agenda_paper ON paper_agenda_items(paper_id);
CREATE INDEX idx_paper_agenda_item ON paper_agenda_items(agenda_item_id);

CREATE TABLE paper_documents (
    paper_id UUID NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_role VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (paper_id, document_id)
);

CREATE TABLE meeting_documents (
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    document_role VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (meeting_id, document_id)
);

-- ============================================
-- HELPER TABLES
-- ============================================

CREATE TABLE scraping_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    scrape_run_id UUID NOT NULL,
    source_url TEXT,
    source_file_path TEXT,
    status VARCHAR(20),
    error_message TEXT,
    records_extracted INTEGER,
    records_inserted INTEGER,
    records_updated INTEGER,
    processing_time_seconds NUMERIC,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_scraping_log_run ON scraping_log(scrape_run_id);
CREATE INDEX idx_scraping_log_status ON scraping_log(status);
CREATE INDEX idx_scraping_log_started ON scraping_log(started_at);

CREATE TABLE data_quality_issues (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    table_name VARCHAR(100),
    record_id UUID,
    field_name VARCHAR(100),
    issue_type VARCHAR(50),
    issue_description TEXT,
    severity VARCHAR(20),
    status VARCHAR(20) DEFAULT 'open',
    resolved_at TIMESTAMP WITH TIME ZONE,
    resolution_note TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_dq_issues_table ON data_quality_issues(table_name);
CREATE INDEX idx_dq_issues_status ON data_quality_issues(status);
CREATE INDEX idx_dq_issues_severity ON data_quality_issues(severity);

-- ============================================
-- VIEWS
-- ============================================

CREATE VIEW v_meetings_full AS
SELECT 
    m.id,
    m.name,
    m.start_time,
    m.location,
    ST_AsGeoJSON(m.location_geometry) as location_geojson,
    m.meeting_status,
    o.name as organization_name,
    o.organization_type,
    COUNT(DISTINCT ai.id) as agenda_items_count,
    COUNT(DISTINCT md.document_id) as documents_count,
    m.source_url
FROM meetings m
LEFT JOIN organizations o ON m.organization_id = o.id
LEFT JOIN agenda_items ai ON ai.meeting_id = m.id
LEFT JOIN meeting_documents md ON md.meeting_id = m.id
GROUP BY m.id, o.name, o.organization_type;

CREATE VIEW v_papers_enriched AS
SELECT 
    p.id,
    p.reference,
    p.name,
    p.paper_type,
    p.date_published,
    oo.name as originator_organization,
    op.family_name as originator_person,
    array_length(p.mentioned_locations, 1) as location_mentions_count,
    COUNT(DISTINCT pd.document_id) as document_count,
    COUNT(DISTINCT pai.agenda_item_id) as agenda_item_count
FROM papers p
LEFT JOIN organizations oo ON p.originator_organization_id = oo.id
LEFT JOIN persons op ON p.originator_person_id = op.id
LEFT JOIN paper_documents pd ON pd.paper_id = p.id
LEFT JOIN paper_agenda_items pai ON pai.paper_id = p.id
GROUP BY p.id, oo.name, op.family_name;

-- ============================================
-- UTILITY FUNCTIONS
-- ============================================

CREATE OR REPLACE FUNCTION get_meeting_statistics(
    org_id UUID, 
    start_date DATE, 
    end_date DATE
)
RETURNS TABLE (
    total_meetings BIGINT,
    total_agenda_items BIGINT,
    total_papers BIGINT,
    avg_agenda_items_per_meeting NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COUNT(DISTINCT m.id)::BIGINT,
        COUNT(DISTINCT ai.id)::BIGINT,
        COUNT(DISTINCT p.id)::BIGINT,
        ROUND(COUNT(DISTINCT ai.id)::NUMERIC / NULLIF(COUNT(DISTINCT m.id), 0), 2)
    FROM meetings m
    LEFT JOIN agenda_items ai ON ai.meeting_id = m.id
    LEFT JOIN paper_agenda_items pai ON pai.agenda_item_id = ai.id
    LEFT JOIN papers p ON p.id = pai.paper_id
    WHERE m.organization_id = org_id
        AND m.start_time::date BETWEEN start_date AND end_date;
END;
$$ LANGUAGE plpgsql;

-- Sample data für Test
INSERT INTO organizations (name, organization_type, short_name) VALUES 
    ('Stadtrat', 'stadtrat', 'SR'),
    ('Bauausschuss', 'ausschuss', 'BA'),
    ('SPD Fraktion', 'fraktion', 'SPD'),
    ('CDU Fraktion', 'fraktion', 'CDU');

COMMENT ON DATABASE stadtrat_db IS 'Ratsinformationssystem Datenbank - HTML-Dump Import';
COMMENT ON TABLE meetings IS 'Stadtratssitzungen und Ausschusssitzungen';
COMMENT ON TABLE agenda_items IS 'Tagesordnungspunkte der Sitzungen';
COMMENT ON TABLE papers IS 'Vorlagen, Anträge, Drucksachen';
COMMENT ON TABLE documents IS 'PDF-Dokumente und Anhänge';
