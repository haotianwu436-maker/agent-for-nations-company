CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    logo_url TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS roles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL
);

CREATE TABLE IF NOT EXISTS user_roles (
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, role_id)
);

CREATE TABLE IF NOT EXISTS report_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id),
    created_by UUID NOT NULL REFERENCES users(id),
    report_type VARCHAR(20) NOT NULL CHECK (report_type IN ('weekly', 'monthly')),
    keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    time_range_start TIMESTAMPTZ NOT NULL,
    time_range_end TIMESTAMPTZ NOT NULL,
    source_whitelist JSONB NOT NULL DEFAULT '[]'::jsonb,
    template_name VARCHAR(100) NOT NULL,
    language VARCHAR(16) NOT NULL DEFAULT 'zh-CN',
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'running', 'success', 'failed')),
    status_message TEXT,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    markdown_content TEXT,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS source_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    source_url TEXT NOT NULL,
    title TEXT NOT NULL,
    source_name VARCHAR(255),
    body_raw TEXT NOT NULL,
    body_cleaned TEXT,
    raw_text TEXT,
    cleaned_text TEXT,
    published_at TIMESTAMPTZ,
    media_name VARCHAR(255),
    fetch_status VARCHAR(20) NOT NULL DEFAULT 'success',
    hash VARCHAR(64),
    content_hash VARCHAR(64),
    dedupe_group VARCHAR(64),
    dedup_status VARCHAR(20) NOT NULL DEFAULT 'kept',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS report_sections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    section_type VARCHAR(50),
    section_key VARCHAR(50) NOT NULL,
    section_title VARCHAR(100) NOT NULL,
    content_markdown TEXT,
    markdown_content TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS citations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    section_key VARCHAR(50) NOT NULL,
    paragraph_index INT NOT NULL DEFAULT 0,
    claim_text TEXT NOT NULL,
    source_item_id UUID REFERENCES source_items(id) ON DELETE SET NULL,
    source_url TEXT NOT NULL,
    quote_text TEXT,
    evidence_snippet TEXT,
    validation_status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS report_charts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES report_jobs(id) ON DELETE CASCADE,
    chart_type VARCHAR(20) NOT NULL,
    title VARCHAR(255) NOT NULL,
    labels JSONB NOT NULL DEFAULT '[]'::jsonb,
    values JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    content TEXT NOT NULL,
    parsed_file_type VARCHAR(20) NOT NULL DEFAULT 'text',
    docling_used BOOLEAN NOT NULL DEFAULT FALSE,
    docling_fallback_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS kb_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    document_id UUID NOT NULL REFERENCES kb_documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    chunk_text TEXT NOT NULL,
    token_count INT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_report_jobs_org_status ON report_jobs(organization_id, status);
CREATE INDEX IF NOT EXISTS idx_source_items_job ON source_items(job_id);
CREATE INDEX IF NOT EXISTS idx_report_sections_job ON report_sections(job_id);
CREATE INDEX IF NOT EXISTS idx_citations_job ON citations(job_id);
CREATE INDEX IF NOT EXISTS idx_report_charts_job ON report_charts(job_id);
CREATE INDEX IF NOT EXISTS idx_kb_documents_org ON kb_documents(organization_id);
CREATE INDEX IF NOT EXISTS idx_kb_chunks_org_doc ON kb_chunks(organization_id, document_id);

INSERT INTO roles (code, name)
VALUES ('owner', '母账号'), ('member', '子账号')
ON CONFLICT (code) DO NOTHING;

DO $$
DECLARE
  org_id UUID;
  owner_id UUID;
BEGIN
  INSERT INTO organizations(name, logo_url) VALUES ('央视网联 AI 媒体实验室', 'https://dummyimage.com/120x40/0f172a/ffffff&text=CCTV+AI')
  RETURNING id INTO org_id;

  INSERT INTO users(organization_id, email, password_hash, display_name)
  VALUES (org_id, 'owner@demo.com', 'demo_hashed_password', '默认母账号')
  RETURNING id INTO owner_id;

  INSERT INTO user_roles(user_id, role_id)
  SELECT owner_id, id FROM roles WHERE code = 'owner';
EXCEPTION
  WHEN unique_violation THEN
    NULL;
END $$;
