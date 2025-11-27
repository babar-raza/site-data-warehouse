-- ============================================
-- Add SERP Queries and CWV Monitored Pages
-- For all Aspose subdomains and major product families
-- ============================================

-- ====================
-- SERP QUERIES
-- ====================

-- Products subdomain (7 product families)
INSERT INTO serp.queries (query_text, property, target_page_path, location, device, is_active)
VALUES
  ('aspose pdf', 'https://products.aspose.net/', '/pdf/', 'United States', 'desktop', true),
  ('aspose words', 'https://products.aspose.net/', '/words/', 'United States', 'desktop', true),
  ('aspose cells', 'https://products.aspose.net/', '/cells/', 'United States', 'desktop', true),
  ('aspose slides', 'https://products.aspose.net/', '/slides/', 'United States', 'desktop', true),
  ('aspose email', 'https://products.aspose.net/', '/email/', 'United States', 'desktop', true),
  ('aspose barcode', 'https://products.aspose.net/', '/barcode/', 'United States', 'desktop', true),
  ('aspose imaging', 'https://products.aspose.net/', '/imaging/', 'United States', 'desktop', true)
ON CONFLICT (query_text, property, target_page_path, location, device) DO NOTHING;

-- Docs subdomain (7 product families)
INSERT INTO serp.queries (query_text, property, target_page_path, location, device, is_active)
VALUES
  ('aspose pdf documentation', 'https://docs.aspose.net/', '/pdf/', 'United States', 'desktop', true),
  ('aspose words documentation', 'https://docs.aspose.net/', '/words/', 'United States', 'desktop', true),
  ('aspose cells documentation', 'https://docs.aspose.net/', '/cells/', 'United States', 'desktop', true),
  ('aspose slides documentation', 'https://docs.aspose.net/', '/slides/', 'United States', 'desktop', true),
  ('aspose email documentation', 'https://docs.aspose.net/', '/email/', 'United States', 'desktop', true),
  ('aspose barcode documentation', 'https://docs.aspose.net/', '/barcode/', 'United States', 'desktop', true),
  ('aspose imaging documentation', 'https://docs.aspose.net/', '/imaging/', 'United States', 'desktop', true)
ON CONFLICT (query_text, property, target_page_path, location, device) DO NOTHING;

-- Reference subdomain (7 product families)
INSERT INTO serp.queries (query_text, property, target_page_path, location, device, is_active)
VALUES
  ('aspose pdf api reference', 'https://reference.aspose.net/', '/pdf/', 'United States', 'desktop', true),
  ('aspose words api reference', 'https://reference.aspose.net/', '/words/', 'United States', 'desktop', true),
  ('aspose cells api reference', 'https://reference.aspose.net/', '/cells/', 'United States', 'desktop', true),
  ('aspose slides api reference', 'https://reference.aspose.net/', '/slides/', 'United States', 'desktop', true),
  ('aspose email api reference', 'https://reference.aspose.net/', '/email/', 'United States', 'desktop', true),
  ('aspose barcode api reference', 'https://reference.aspose.net/', '/barcode/', 'United States', 'desktop', true),
  ('aspose imaging api reference', 'https://reference.aspose.net/', '/imaging/', 'United States', 'desktop', true)
ON CONFLICT (query_text, property, target_page_path, location, device) DO NOTHING;

-- Blog subdomain (7 product families)
INSERT INTO serp.queries (query_text, property, target_page_path, location, device, is_active)
VALUES
  ('aspose pdf blog', 'https://blog.aspose.net/', '/pdf/', 'United States', 'desktop', true),
  ('aspose words blog', 'https://blog.aspose.net/', '/words/', 'United States', 'desktop', true),
  ('aspose cells blog', 'https://blog.aspose.net/', '/cells/', 'United States', 'desktop', true),
  ('aspose slides blog', 'https://blog.aspose.net/', '/slides/', 'United States', 'desktop', true),
  ('aspose email blog', 'https://blog.aspose.net/', '/email/', 'United States', 'desktop', true),
  ('aspose barcode blog', 'https://blog.aspose.net/', '/barcode/', 'United States', 'desktop', true),
  ('aspose imaging blog', 'https://blog.aspose.net/', '/imaging/', 'United States', 'desktop', true)
ON CONFLICT (query_text, property, target_page_path, location, device) DO NOTHING;

-- KB subdomain (7 product families)
INSERT INTO serp.queries (query_text, property, target_page_path, location, device, is_active)
VALUES
  ('aspose pdf knowledge base', 'https://kb.aspose.net/', '/pdf/', 'United States', 'desktop', true),
  ('aspose words knowledge base', 'https://kb.aspose.net/', '/words/', 'United States', 'desktop', true),
  ('aspose cells knowledge base', 'https://kb.aspose.net/', '/cells/', 'United States', 'desktop', true),
  ('aspose slides knowledge base', 'https://kb.aspose.net/', '/slides/', 'United States', 'desktop', true),
  ('aspose email knowledge base', 'https://kb.aspose.net/', '/email/', 'United States', 'desktop', true),
  ('aspose barcode knowledge base', 'https://kb.aspose.net/', '/barcode/', 'United States', 'desktop', true),
  ('aspose imaging knowledge base', 'https://kb.aspose.net/', '/imaging/', 'United States', 'desktop', true)
ON CONFLICT (query_text, property, target_page_path, location, device) DO NOTHING;

-- ====================
-- CWV MONITORED PAGES
-- ====================

-- Products subdomain (7 product families) - Desktop + Mobile
INSERT INTO performance.monitored_pages (property, page_path, page_name, check_mobile, check_desktop, is_active)
VALUES
  ('https://products.aspose.net/', '/pdf/', 'Products - PDF Family', true, true, true),
  ('https://products.aspose.net/', '/words/', 'Products - Words Family', true, true, true),
  ('https://products.aspose.net/', '/cells/', 'Products - Cells Family', true, true, true),
  ('https://products.aspose.net/', '/slides/', 'Products - Slides Family', true, true, true),
  ('https://products.aspose.net/', '/email/', 'Products - Email Family', true, true, true),
  ('https://products.aspose.net/', '/barcode/', 'Products - Barcode Family', true, true, true),
  ('https://products.aspose.net/', '/imaging/', 'Products - Imaging Family', true, true, true)
ON CONFLICT (property, page_path) DO UPDATE
SET page_name = EXCLUDED.page_name,
    check_mobile = EXCLUDED.check_mobile,
    check_desktop = EXCLUDED.check_desktop,
    is_active = EXCLUDED.is_active;

-- Docs subdomain (7 product families) - Mobile only (faster page loads)
INSERT INTO performance.monitored_pages (property, page_path, page_name, check_mobile, check_desktop, is_active)
VALUES
  ('https://docs.aspose.net/', '/pdf/', 'Docs - PDF Family', true, false, true),
  ('https://docs.aspose.net/', '/words/', 'Docs - Words Family', true, false, true),
  ('https://docs.aspose.net/', '/cells/', 'Docs - Cells Family', true, false, true),
  ('https://docs.aspose.net/', '/slides/', 'Docs - Slides Family', true, false, true),
  ('https://docs.aspose.net/', '/email/', 'Docs - Email Family', true, false, true),
  ('https://docs.aspose.net/', '/barcode/', 'Docs - Barcode Family', true, false, true),
  ('https://docs.aspose.net/', '/imaging/', 'Docs - Imaging Family', true, false, true)
ON CONFLICT (property, page_path) DO UPDATE
SET page_name = EXCLUDED.page_name,
    check_mobile = EXCLUDED.check_mobile,
    check_desktop = EXCLUDED.check_desktop,
    is_active = EXCLUDED.is_active;

-- Reference subdomain (7 product families) - Mobile only
INSERT INTO performance.monitored_pages (property, page_path, page_name, check_mobile, check_desktop, is_active)
VALUES
  ('https://reference.aspose.net/', '/pdf/', 'Reference - PDF API', true, false, true),
  ('https://reference.aspose.net/', '/words/', 'Reference - Words API', true, false, true),
  ('https://reference.aspose.net/', '/cells/', 'Reference - Cells API', true, false, true),
  ('https://reference.aspose.net/', '/slides/', 'Reference - Slides API', true, false, true),
  ('https://reference.aspose.net/', '/email/', 'Reference - Email API', true, false, true),
  ('https://reference.aspose.net/', '/barcode/', 'Reference - Barcode API', true, false, true),
  ('https://reference.aspose.net/', '/imaging/', 'Reference - Imaging API', true, false, true)
ON CONFLICT (property, page_path) DO UPDATE
SET page_name = EXCLUDED.page_name,
    check_mobile = EXCLUDED.check_mobile,
    check_desktop = EXCLUDED.check_desktop,
    is_active = EXCLUDED.is_active;

-- Blog subdomain (7 product families) - Mobile only
INSERT INTO performance.monitored_pages (property, page_path, page_name, check_mobile, check_desktop, is_active)
VALUES
  ('https://blog.aspose.net/', '/pdf/', 'Blog - PDF Category', true, false, true),
  ('https://blog.aspose.net/', '/words/', 'Blog - Words Category', true, false, true),
  ('https://blog.aspose.net/', '/cells/', 'Blog - Cells Category', true, false, true),
  ('https://blog.aspose.net/', '/slides/', 'Blog - Slides Category', true, false, true),
  ('https://blog.aspose.net/', '/email/', 'Blog - Email Category', true, false, true),
  ('https://blog.aspose.net/', '/barcode/', 'Blog - Barcode Category', true, false, true),
  ('https://blog.aspose.net/', '/imaging/', 'Blog - Imaging Category', true, false, true)
ON CONFLICT (property, page_path) DO UPDATE
SET page_name = EXCLUDED.page_name,
    check_mobile = EXCLUDED.check_mobile,
    check_desktop = EXCLUDED.check_desktop,
    is_active = EXCLUDED.is_active;

-- KB subdomain (7 product families) - Mobile only
INSERT INTO performance.monitored_pages (property, page_path, page_name, check_mobile, check_desktop, is_active)
VALUES
  ('https://kb.aspose.net/', '/pdf/', 'KB - PDF Category', true, false, true),
  ('https://kb.aspose.net/', '/words/', 'KB - Words Category', true, false, true),
  ('https://kb.aspose.net/', '/cells/', 'KB - Cells Category', true, false, true),
  ('https://kb.aspose.net/', '/slides/', 'KB - Slides Category', true, false, true),
  ('https://kb.aspose.net/', '/email/', 'KB - Email Category', true, false, true),
  ('https://kb.aspose.net/', '/barcode/', 'KB - Barcode Category', true, false, true),
  ('https://kb.aspose.net/', '/imaging/', 'KB - Imaging Category', true, false, true)
ON CONFLICT (property, page_path) DO UPDATE
SET page_name = EXCLUDED.page_name,
    check_mobile = EXCLUDED.check_mobile,
    check_desktop = EXCLUDED.check_desktop,
    is_active = EXCLUDED.is_active;

-- ====================
-- SUMMARY
-- ====================

-- Count SERP queries
SELECT 'SERP Queries Added' as metric, COUNT(*) as count
FROM serp.queries
WHERE is_active = true;

-- Count CWV pages
SELECT 'CWV Pages Added' as metric, COUNT(*) as count
FROM performance.monitored_pages
WHERE is_active = true;

-- List all SERP queries by subdomain
SELECT
    SPLIT_PART(property, '://', 2) as subdomain,
    COUNT(*) as query_count
FROM serp.queries
WHERE is_active = true
GROUP BY subdomain
ORDER BY subdomain;

-- List all CWV pages by subdomain
SELECT
    SPLIT_PART(property, '://', 2) as subdomain,
    COUNT(*) as page_count,
    SUM(CASE WHEN check_mobile THEN 1 ELSE 0 END) as mobile_checks,
    SUM(CASE WHEN check_desktop THEN 1 ELSE 0 END) as desktop_checks
FROM performance.monitored_pages
WHERE is_active = true
GROUP BY subdomain
ORDER BY subdomain;
