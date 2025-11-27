-- =============================================
-- POSTGRESQL EXTENSIONS
-- =============================================
-- Purpose: Enable advanced PostgreSQL features
-- Dependencies: PostgreSQL 14+
-- Run: Before any other schema scripts

SET search_path TO public;

-- =============================================
-- VECTOR EXTENSION (for embeddings & semantic search)
-- =============================================
-- Enables storage and similarity search of vector embeddings
-- Used for: content similarity, cannibalization detection, topic clustering
CREATE EXTENSION IF NOT EXISTS vector;

COMMENT ON EXTENSION vector IS 'Vector similarity search for content embeddings (pgvector)';

-- =============================================
-- TRIGRAM EXTENSION (for fuzzy text matching)
-- =============================================
-- Enables fast fuzzy text search and similarity
-- Used for: page path matching, query deduplication
CREATE EXTENSION IF NOT EXISTS pg_trgm;

COMMENT ON EXTENSION pg_trgm IS 'Trigram-based text similarity and indexing';

-- =============================================
-- UUID EXTENSION (for unique identifiers)
-- =============================================
-- Enables UUID generation (if not already enabled)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

COMMENT ON EXTENSION "uuid-ossp" IS 'UUID generation functions';

-- =============================================
-- TABLEFUNC EXTENSION (for advanced analytics)
-- =============================================
-- Enables crosstab and other advanced table functions
-- Used for: pivot tables, time-series analysis
CREATE EXTENSION IF NOT EXISTS tablefunc;

COMMENT ON EXTENSION tablefunc IS 'Advanced table manipulation functions';

-- =============================================
-- VERIFY EXTENSIONS
-- =============================================
DO $$
DECLARE
    missing_extensions TEXT[];
BEGIN
    SELECT ARRAY_AGG(ext) INTO missing_extensions
    FROM (
        SELECT unnest(ARRAY['vector', 'pg_trgm', 'uuid-ossp', 'tablefunc']) AS ext
    ) e
    WHERE NOT EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = e.ext
    );

    IF array_length(missing_extensions, 1) > 0 THEN
        RAISE WARNING 'Missing extensions: %', array_to_string(missing_extensions, ', ');
    ELSE
        RAISE NOTICE 'All required extensions are installed ✓';
    END IF;
END $$;

-- =============================================
-- EXTENSION USAGE EXAMPLES
-- =============================================
/*
-- Vector similarity (cosine distance)
SELECT page_path, 1 - (embedding <=> query_embedding) AS similarity
FROM content.page_snapshots
ORDER BY similarity DESC
LIMIT 10;

-- Fuzzy text search
SELECT page_path, similarity(page_path, '/blog/python') AS sim
FROM gsc.fact_gsc_daily
WHERE page_path % '/blog/python'
ORDER BY sim DESC;

-- UUID generation
SELECT uuid_generate_v4();

-- Crosstab pivot
SELECT * FROM crosstab(
    'SELECT date, metric, value FROM metrics ORDER BY 1,2',
    'SELECT DISTINCT metric FROM metrics ORDER BY 1'
) AS ct(date DATE, clicks INT, impressions INT);
*/
