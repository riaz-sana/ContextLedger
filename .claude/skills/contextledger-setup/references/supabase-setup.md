# Supabase Setup for ContextLedger

Run this SQL once in your Supabase project's SQL Editor (Dashboard > SQL Editor):

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS contextledger_findings (
    id TEXT PRIMARY KEY,
    skill_profile TEXT NOT NULL,
    skill_version TEXT NOT NULL DEFAULT '',
    finding_type TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    confidence FLOAT NOT NULL DEFAULT 0.5,
    domain TEXT NOT NULL DEFAULT '',
    "timestamp" TIMESTAMPTZ DEFAULT NOW(),
    evaluation_eligible BOOLEAN DEFAULT TRUE,
    embedding VECTOR(1536),
    tags JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_findings_profile
    ON contextledger_findings(skill_profile);

-- Required for Row Level Security
ALTER TABLE contextledger_findings DISABLE ROW LEVEL SECURITY;
-- Or if you prefer to keep RLS:
-- CREATE POLICY "Allow all operations" ON contextledger_findings
--     FOR ALL USING (true) WITH CHECK (true);

CREATE OR REPLACE FUNCTION match_findings(
    query_embedding VECTOR(1536),
    match_count INT,
    profile_filter TEXT DEFAULT NULL
) RETURNS TABLE (
    id TEXT, skill_profile TEXT, summary TEXT,
    confidence FLOAT, domain TEXT, "timestamp" TIMESTAMPTZ,
    similarity FLOAT
) LANGUAGE SQL STABLE AS $$
    SELECT id, skill_profile, summary, confidence, domain, "timestamp",
           1 - (embedding <=> query_embedding) AS similarity
    FROM contextledger_findings
    WHERE (profile_filter IS NULL OR skill_profile = profile_filter)
      AND evaluation_eligible = TRUE
    ORDER BY embedding <=> query_embedding
    LIMIT match_count;
$$;
```

After running the SQL, get your credentials from Settings > API:
- **Project URL** — looks like `https://xxxxx.supabase.co`
- **Anon key** — starts with `eyJ...`

Add both to the project's `.env` file:
```
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
```
