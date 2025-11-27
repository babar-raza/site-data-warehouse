#!/usr/bin/env python3
"""
Add monitoring pages for all Aspose subdomains and product families
"""
import os
import psycopg2

# Subdomain configuration
SUBDOMAINS_WITH_FAMILIES = [
    'products.aspose.net',
    'docs.aspose.net',
    'reference.aspose.net',
    'blog.aspose.net',
    'kb.aspose.net'
]

# Product families (14 total - slides excluded as it doesn't exist)
PRODUCT_FAMILIES = [
    ('/pdf/', 'PDF'),
    ('/words/', 'Words'),
    ('/cells/', 'Cells'),
    ('/email/', 'Email'),
    ('/imaging/', 'Imaging'),
    ('/barcode/', 'Barcode'),
    ('/tasks/', 'Tasks'),
    ('/ocr/', 'OCR'),
    ('/cad/', 'CAD'),
    ('/html/', 'HTML'),
    ('/zip/', 'ZIP'),
    ('/page/', 'Page'),
    ('/psd/', 'PSD'),
    ('/svg/', 'SVG'),
    ('/tex/', 'TeX')
]

# Query keywords by subdomain
QUERY_KEYWORDS = {
    'products.aspose.net': 'aspose {}',
    'docs.aspose.net': 'aspose {} documentation',
    'reference.aspose.net': 'aspose {} api reference',
    'blog.aspose.net': 'aspose {} blog',
    'kb.aspose.net': 'aspose {} knowledge base'
}

def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        database=os.environ.get('DB_NAME', 'gsc_db'),
        user=os.environ.get('DB_USER', 'gsc_user'),
        password=os.environ.get('DB_PASSWORD', 'gsc_pass_secure_2024')
    )

def add_serp_queries(conn):
    """Add SERP tracking queries"""
    added = 0
    skipped = 0

    for subdomain in SUBDOMAINS_WITH_FAMILIES:
        property_url = f'https://{subdomain}'  # Remove trailing slash
        keyword_template = QUERY_KEYWORDS[subdomain]

        for family_path, family_name in PRODUCT_FAMILIES:
            query_text = keyword_template.format(family_name.lower())

            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO serp.queries
                        (query_text, property, target_page_path, location, device, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (property, query_text, location, device) DO NOTHING
                        RETURNING query_id
                    """, (query_text, property_url, family_path, 'United States', 'desktop', True))

                    if cur.rowcount > 0:
                        print(f"  + Added SERP query: {query_text} -> {property_url}{family_path}")
                        added += 1
                    else:
                        print(f"  - Skipped (exists): {query_text}")
                        skipped += 1

                conn.commit()
            except Exception as e:
                print(f"  X Error adding {query_text}: {e}")
                conn.rollback()

    return added, skipped

def add_cwv_pages(conn):
    """Add CWV monitored pages"""
    added = 0
    skipped = 0

    for subdomain in SUBDOMAINS_WITH_FAMILIES:
        property_url = f'https://{subdomain}'  # Remove trailing slash

        # Products gets desktop + mobile, others get mobile only
        check_desktop = (subdomain == 'products.aspose.net')

        for family_path, family_name in PRODUCT_FAMILIES:
            page_name = f"{subdomain.split('.')[0].title()} - {family_name} Family"

            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO performance.monitored_pages
                        (property, page_path, page_name, check_mobile, check_desktop, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (property, page_path) DO UPDATE
                        SET page_name = EXCLUDED.page_name,
                            check_mobile = EXCLUDED.check_mobile,
                            check_desktop = EXCLUDED.check_desktop,
                            is_active = EXCLUDED.is_active
                        RETURNING page_id
                    """, (property_url, family_path, page_name, True, check_desktop, True))

                    if cur.rowcount > 0:
                        print(f"  + Added CWV page: {property_url}{family_path}")
                        added += 1
                    else:
                        print(f"  - Skipped (exists): {property_url}{family_path}")
                        skipped += 1

                conn.commit()
            except Exception as e:
                print(f"  X Error adding {property_url}{family_path}: {e}")
                conn.rollback()

    return added, skipped

def main():
    print("=== Adding Monitoring Pages ===\n")

    conn = get_db_connection()

    try:
        # Add SERP queries
        print("Adding SERP Queries...")
        serp_added, serp_skipped = add_serp_queries(conn)

        print(f"\nSERP Queries: {serp_added} added, {serp_skipped} skipped")

        # Add CWV pages
        print("\nAdding CWV Monitored Pages...")
        cwv_added, cwv_skipped = add_cwv_pages(conn)

        print(f"\nCWV Pages: {cwv_added} added, {cwv_skipped} skipped")

        # Summary
        print("\n" + "=" * 50)
        print("SUMMARY")
        print("=" * 50)

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM serp.queries WHERE is_active = true")
            total_serp = cur.fetchone()[0]

            cur.execute("SELECT COUNT(*) FROM performance.monitored_pages WHERE is_active = true")
            total_cwv = cur.fetchone()[0]

        print(f"Total Active SERP Queries:  {total_serp}")
        print(f"Total Active CWV Pages:     {total_cwv}")
        print("\nDone!")

    finally:
        conn.close()

if __name__ == '__main__':
    main()
