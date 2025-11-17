-- =============================================
-- SECURITY CONFIGURATION (OPTIONAL FOR DEV)
-- =============================================
-- Database security hardening - optional for localhost/development
-- 
-- To enable strict security (production):
--   SET app.security_mode = 'production';
--
-- For development (relaxed security):
--   SET app.security_mode = 'development';  -- default
--
-- Features:
-- - Least privilege users (optional)
-- - Row-Level Security (optional in dev)
-- - Audit logging (optional in dev)
-- - SSL/TLS (optional for localhost)

SET search_path TO gsc, public;

-- =============================================
-- SECURITY MODE DETECTION
-- =============================================

DO $$
DECLARE
    security_mode TEXT;
BEGIN
    -- Check for security mode setting
    BEGIN
        security_mode := current_setting('app.security_mode', TRUE);
    EXCEPTION
        WHEN OTHERS THEN
            security_mode := 'development';  -- Default to development
    END;
    
    -- Fallback to environment variable if not set
    IF security_mode IS NULL OR security_mode = '' THEN
        security_mode := COALESCE(
            current_setting('SECURITY_MODE', TRUE),
            'development'
        );
    END IF;
    
    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Security Mode: %', security_mode;
    RAISE NOTICE '============================================';
    RAISE NOTICE '';
    
    IF security_mode = 'development' THEN
        RAISE NOTICE 'Running in DEVELOPMENT mode:';
        RAISE NOTICE '  - Relaxed security policies';
        RAISE NOTICE '  - SSL not required';
        RAISE NOTICE '  - Row-Level Security optional';
        RAISE NOTICE '  - Audit logging optional';
        RAISE NOTICE '';
        RAISE NOTICE 'For PRODUCTION, set: app.security_mode = ''production''';
        RAISE NOTICE '';
    ELSE
        RAISE NOTICE 'Running in PRODUCTION mode:';
        RAISE NOTICE '  - Strict security policies';
        RAISE NOTICE '  - SSL recommended';
        RAISE NOTICE '  - Row-Level Security enabled';
        RAISE NOTICE '  - Audit logging enabled';
        RAISE NOTICE '';
    END IF;
END $$;

-- =============================================
-- 1. CREATE RESTRICTED USERS (OPTIONAL)
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    -- Only create additional users if explicitly requested
    IF security_mode = 'production' THEN
        -- Read-only user
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
            CREATE USER gsc_readonly WITH PASSWORD NULL;
            RAISE NOTICE 'Created user: gsc_readonly';
        END IF;
        
        -- Application user
        IF NOT EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_app') THEN
            CREATE USER gsc_app WITH PASSWORD NULL;
            RAISE NOTICE 'Created user: gsc_app';
        END IF;
    ELSE
        RAISE NOTICE 'Skipping additional user creation (development mode)';
        RAISE NOTICE '  In dev, gsc_user is sufficient for all operations';
    END IF;
END $$;

-- =============================================
-- 2. GRANT MINIMAL PRIVILEGES (OPTIONAL)
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    IF security_mode = 'production' THEN
        -- Read-only user permissions
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
            GRANT CONNECT ON DATABASE gsc_db TO gsc_readonly;
            GRANT USAGE ON SCHEMA gsc TO gsc_readonly;
            GRANT SELECT ON ALL TABLES IN SCHEMA gsc TO gsc_readonly;
            GRANT SELECT ON ALL SEQUENCES IN SCHEMA gsc TO gsc_readonly;
            ALTER DEFAULT PRIVILEGES IN SCHEMA gsc GRANT SELECT ON TABLES TO gsc_readonly;
            RAISE NOTICE '✓ Granted read-only permissions';
        END IF;
        
        -- Application user permissions
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_app') THEN
            GRANT CONNECT ON DATABASE gsc_db TO gsc_app;
            GRANT USAGE ON SCHEMA gsc TO gsc_app;
            GRANT SELECT ON ALL TABLES IN SCHEMA gsc TO gsc_app;
            GRANT INSERT, UPDATE, DELETE ON gsc.insights TO gsc_app;
            GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA gsc TO gsc_app;
            RAISE NOTICE '✓ Granted application permissions';
        END IF;
        
        -- Revoke dangerous permissions
        REVOKE CREATE ON SCHEMA gsc FROM PUBLIC;
        REVOKE ALL ON SCHEMA public FROM PUBLIC;
        RAISE NOTICE '✓ Revoked public permissions';
    ELSE
        RAISE NOTICE 'Skipping permission restrictions (development mode)';
    END IF;
END $$;

-- =============================================
-- 3. ROW-LEVEL SECURITY (OPTIONAL IN DEV)
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    IF security_mode = 'production' THEN
        -- Enable RLS on insights table
        ALTER TABLE gsc.insights ENABLE ROW LEVEL SECURITY;
        
        -- Policy: Users can only see insights for their properties
        DROP POLICY IF EXISTS insights_property_isolation ON gsc.insights;
        CREATE POLICY insights_property_isolation ON gsc.insights
            FOR SELECT
            USING (
                current_user = 'gsc_user'
                OR
                property = current_setting('app.current_property', TRUE)
            );
        
        -- Policy: Application can insert insights
        DROP POLICY IF EXISTS insights_app_insert ON gsc.insights;
        CREATE POLICY insights_app_insert ON gsc.insights
            FOR INSERT
            TO gsc_app
            WITH CHECK (true);
        
        RAISE NOTICE '✓ Row-Level Security enabled';
    ELSE
        RAISE NOTICE 'Skipping Row-Level Security (development mode)';
        RAISE NOTICE '  RLS can slow down queries during development';
    END IF;
END $$;

-- =============================================
-- 4. AUDIT LOGGING (OPTIONAL IN DEV)
-- =============================================

-- Create audit log table (always, but optional to use)
CREATE TABLE IF NOT EXISTS gsc.audit_log (
    id SERIAL PRIMARY KEY,
    event_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    user_name TEXT,
    event_type TEXT,
    object_schema TEXT,
    object_name TEXT,
    query_text TEXT,
    client_addr INET,
    success BOOLEAN
);

CREATE OR REPLACE FUNCTION gsc.audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO gsc.audit_log (
        user_name,
        event_type,
        object_schema,
        object_name,
        success
    ) VALUES (
        current_user,
        TG_OP,
        TG_TABLE_SCHEMA,
        TG_TABLE_NAME,
        true
    );
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    IF security_mode = 'production' THEN
        -- Apply audit triggers
        DROP TRIGGER IF EXISTS audit_insights_changes ON gsc.insights;
        CREATE TRIGGER audit_insights_changes
            AFTER INSERT OR UPDATE OR DELETE ON gsc.insights
            FOR EACH ROW EXECUTE FUNCTION gsc.audit_trigger_func();
        
        -- Prevent tampering
        REVOKE ALL ON gsc.audit_log FROM PUBLIC;
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
            GRANT SELECT ON gsc.audit_log TO gsc_readonly;
        END IF;
        REVOKE DELETE, TRUNCATE ON gsc.audit_log FROM gsc_user;
        
        RAISE NOTICE '✓ Audit logging enabled';
    ELSE
        RAISE NOTICE 'Audit log table created but triggers not enabled (development mode)';
        RAISE NOTICE '  Enable manually if needed for debugging';
    END IF;
END $$;

-- =============================================
-- 5. SENSITIVE DATA PROTECTION (ALWAYS)
-- =============================================

-- Mask API keys in insights (always useful)
CREATE OR REPLACE FUNCTION gsc.mask_sensitive_data(data JSONB)
RETURNS JSONB AS $$
BEGIN
    RETURN jsonb_set(
        data,
        '{api_key}',
        to_jsonb('***REDACTED***'::TEXT),
        false
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- View for safe insights access
CREATE OR REPLACE VIEW gsc.vw_insights_safe AS
SELECT 
    id,
    property,
    category,
    title,
    description,
    severity,
    confidence,
    entity_id,
    entity_type,
    gsc.mask_sensitive_data(metrics) as metrics,
    actions,
    source,
    generated_at,
    expires_at
FROM gsc.insights;

-- Grant access to readonly user if exists
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
        GRANT SELECT ON gsc.vw_insights_safe TO gsc_readonly;
    END IF;
END $$;

RAISE NOTICE '✓ Sensitive data masking configured';

-- =============================================
-- 6. CONNECTION SECURITY (OPTIONAL SSL)
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    IF security_mode = 'production' THEN
        RAISE NOTICE 'PRODUCTION: Configure SSL in postgresql.conf and pg_hba.conf';
        RAISE NOTICE '  ssl = on';
        RAISE NOTICE '  ssl_min_protocol_version = ''TLSv1.2''';
    ELSE
        RAISE NOTICE 'DEVELOPMENT: SSL not required for localhost connections';
    END IF;
    
    -- Connection limits (always useful)
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
        ALTER USER gsc_readonly CONNECTION LIMIT 10;
    END IF;
    IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_app') THEN
        ALTER USER gsc_app CONNECTION LIMIT 20;
    END IF;
END $$;

-- =============================================
-- 7. PASSWORD POLICIES (OPTIONAL IN DEV)
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    IF security_mode = 'production' THEN
        -- Set password expiration (90 days)
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_readonly') THEN
            ALTER USER gsc_readonly VALID UNTIL (CURRENT_DATE + INTERVAL '90 days');
        END IF;
        IF EXISTS (SELECT FROM pg_user WHERE usename = 'gsc_app') THEN
            ALTER USER gsc_app VALID UNTIL (CURRENT_DATE + INTERVAL '90 days');
        END IF;
        RAISE NOTICE '✓ Password expiration set (90 days)';
    ELSE
        RAISE NOTICE 'Skipping password expiration (development mode)';
    END IF;
END $$;

-- =============================================
-- 8. SECURITY FUNCTIONS (ALWAYS AVAILABLE)
-- =============================================

CREATE OR REPLACE FUNCTION gsc.is_password_strong(password TEXT)
RETURNS BOOLEAN AS $$
BEGIN
    RETURN (
        LENGTH(password) >= 16 AND
        password ~ '[A-Z]' AND
        password ~ '[a-z]' AND
        password ~ '[0-9]' AND
        password ~ '[^A-Za-z0-9]'
    );
END;
$$ LANGUAGE plpgsql IMMUTABLE;

CREATE OR REPLACE FUNCTION gsc.check_failed_logins(check_user TEXT, time_window INTERVAL DEFAULT '1 hour')
RETURNS INTEGER AS $$
DECLARE
    failed_count INTEGER;
BEGIN
    SELECT COUNT(*)
    INTO failed_count
    FROM gsc.audit_log
    WHERE user_name = check_user
        AND event_type = 'LOGIN_FAILED'
        AND event_time > (CURRENT_TIMESTAMP - time_window);
    
    RETURN failed_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

RAISE NOTICE '✓ Security utility functions created';

-- =============================================
-- DOCUMENTATION
-- =============================================

COMMENT ON TABLE gsc.audit_log IS 
'Audit trail for security-relevant operations. Enabled in production mode.';

COMMENT ON FUNCTION gsc.mask_sensitive_data(JSONB) IS 
'Masks sensitive data in JSON fields for safe display.';

-- =============================================
-- FINAL SUMMARY
-- =============================================

DO $$
DECLARE
    security_mode TEXT := COALESCE(current_setting('app.security_mode', TRUE), 'development');
BEGIN
    RAISE NOTICE '';
    RAISE NOTICE '============================================';
    RAISE NOTICE 'Security Configuration Complete';
    RAISE NOTICE '============================================';
    RAISE NOTICE '';
    
    IF security_mode = 'development' THEN
        RAISE NOTICE 'DEVELOPMENT MODE ENABLED';
        RAISE NOTICE '';
        RAISE NOTICE 'Security features:';
        RAISE NOTICE '  ✓ Sensitive data masking';
        RAISE NOTICE '  ✓ Audit log table created';
        RAISE NOTICE '  ⊘ Row-Level Security disabled';
        RAISE NOTICE '  ⊘ Additional users not created';
        RAISE NOTICE '  ⊘ Password policies relaxed';
        RAISE NOTICE '  ⊘ SSL not required';
        RAISE NOTICE '';
        RAISE NOTICE 'To enable production security:';
        RAISE NOTICE '  SET app.security_mode = ''production'';';
        RAISE NOTICE '  Then re-run this script';
    ELSE
        RAISE NOTICE 'PRODUCTION MODE ENABLED';
        RAISE NOTICE '';
        RAISE NOTICE 'Security features:';
        RAISE NOTICE '  ✓ Sensitive data masking';
        RAISE NOTICE '  ✓ Audit logging active';
        RAISE NOTICE '  ✓ Row-Level Security enabled';
        RAISE NOTICE '  ✓ Additional users created';
        RAISE NOTICE '  ✓ Password policies enforced';
        RAISE NOTICE '  ✓ Connection limits set';
        RAISE NOTICE '';
        RAISE NOTICE 'Next steps:';
        RAISE NOTICE '  1. Set passwords for all users';
        RAISE NOTICE '  2. Configure SSL certificates';
        RAISE NOTICE '  3. Review audit_log regularly';
        RAISE NOTICE '  4. Rotate passwords every 90 days';
    END IF;
    
    RAISE NOTICE '';
END $$;
