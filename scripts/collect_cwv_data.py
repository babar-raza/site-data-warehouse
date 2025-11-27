#!/usr/bin/env python3
"""
Core Web Vitals Monitoring - PageSpeed Insights Integration
Collects CWV metrics and Lighthouse scores for tracked pages
"""
import os
import sys
import time
import requests
import psycopg2
import psycopg2.extras
from datetime import date
from typing import List, Dict, Optional

# Database connection
def get_db_connection():
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', 5432)),
        database=os.environ.get('DB_NAME', 'gsc_db'),
        user=os.environ.get('DB_USER', 'gsc_user'),
        password=os.environ.get('DB_PASSWORD', 'gsc_pass_secure_2024')
    )

def get_monitored_pages():
    """Get active pages to monitor"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT page_id, property, page_path, page_name, check_mobile, check_desktop
                FROM performance.monitored_pages
                WHERE is_active = true
            """)
            return cur.fetchall()
    finally:
        conn.close()

def run_pagespeed_insights(url: str, strategy: str = 'mobile') -> Optional[Dict]:
    """Query PageSpeed Insights API"""
    api_key = os.environ.get('PAGESPEED_API_KEY', '')

    if not api_key:
        print("⚠ Warning: PAGESPEED_API_KEY not set. API has strict rate limits without a key.")

    base_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        'url': url,
        'strategy': strategy,
        'category': ['performance', 'accessibility', 'best-practices', 'seo', 'pwa']
    }

    if api_key:
        params['key'] = api_key

    try:
        response = requests.get(base_url, params=params, timeout=60)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            print(f"✗ Rate limit exceeded for {url}")
        elif e.response.status_code == 400:
            print(f"✗ Invalid URL or bad request: {url}")
        else:
            print(f"✗ HTTP error {e.response.status_code} for {url}")
        return None
    except Exception as e:
        print(f"✗ Error querying PageSpeed Insights for {url}: {e}")
        return None

def extract_cwv_metrics(result: Dict) -> Dict:
    """Extract Core Web Vitals and Lighthouse scores from PSI result"""
    lighthouse = result.get('lighthouseResult', {})
    audits = lighthouse.get('audits', {})
    categories = lighthouse.get('categories', {})

    # Core Web Vitals
    lcp = audits.get('largest-contentful-paint', {}).get('numericValue')
    fid = audits.get('max-potential-fid', {}).get('numericValue')  # FID deprecated, use max-potential-fid
    cls = audits.get('cumulative-layout-shift', {}).get('numericValue')
    fcp = audits.get('first-contentful-paint', {}).get('numericValue')
    inp = audits.get('interaction-to-next-paint', {}).get('numericValue')
    ttfb = audits.get('server-response-time', {}).get('numericValue')
    tti = audits.get('interactive', {}).get('numericValue')
    tbt = audits.get('total-blocking-time', {}).get('numericValue')
    speed_index = audits.get('speed-index', {}).get('numericValue')

    # Convert milliseconds to seconds for display metrics
    if lcp:
        lcp = lcp / 1000
    if fid:
        fid = fid / 1000
    if fcp:
        fcp = fcp / 1000
    if inp:
        inp = inp / 1000
    if ttfb:
        ttfb = ttfb / 1000
    if tti:
        tti = tti / 1000
    if tbt:
        tbt = tbt / 1000
    if speed_index:
        speed_index = speed_index / 1000

    # Lighthouse scores (0-100)
    performance_score = int(categories.get('performance', {}).get('score', 0) * 100)
    accessibility_score = int(categories.get('accessibility', {}).get('score', 0) * 100)
    best_practices_score = int(categories.get('best-practices', {}).get('score', 0) * 100)
    seo_score = int(categories.get('seo', {}).get('score', 0) * 100)
    pwa_score = int(categories.get('pwa', {}).get('score', 0) * 100) if 'pwa' in categories else None

    # CWV Assessment
    cwv_assessment = result.get('loadingExperience', {}).get('overall_category', 'UNKNOWN')

    # Opportunities and diagnostics
    opportunities = []
    diagnostics = []

    for audit_id, audit in audits.items():
        if audit.get('scoreDisplayMode') == 'numeric' and audit.get('score', 1) < 0.9:
            if 'savings' in str(audit.get('details', {})):
                opportunities.append({
                    'id': audit_id,
                    'title': audit.get('title'),
                    'description': audit.get('description'),
                    'score': audit.get('score')
                })
            else:
                diagnostics.append({
                    'id': audit_id,
                    'title': audit.get('title'),
                    'description': audit.get('description'),
                    'score': audit.get('score')
                })

    return {
        'lcp': lcp,
        'fid': fid,
        'cls': cls,
        'fcp': fcp,
        'inp': inp,
        'ttfb': ttfb,
        'tti': tti,
        'tbt': tbt,
        'speed_index': speed_index,
        'performance_score': performance_score,
        'accessibility_score': accessibility_score,
        'best_practices_score': best_practices_score,
        'seo_score': seo_score,
        'pwa_score': pwa_score,
        'cwv_assessment': cwv_assessment,
        'opportunities': opportunities,
        'diagnostics': diagnostics,
        'lighthouse_version': lighthouse.get('lighthouseVersion'),
        'user_agent': lighthouse.get('userAgent')
    }

def save_cwv_data(page_id: str, property: str, page_path: str, strategy: str, metrics: Dict):
    """Save CWV metrics to database"""
    # Normalize property URL (remove trailing slash)
    property = property.rstrip('/')

    conn = get_db_connection()
    try:
        check_date = date.today()

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO performance.core_web_vitals
                (property, page_path, check_date, strategy,
                 lcp, fid, cls, fcp, inp, ttfb, tti, tbt, speed_index,
                 performance_score, accessibility_score, best_practices_score, seo_score, pwa_score,
                 cwv_assessment, opportunities, diagnostics, lighthouse_version, user_agent)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (property, page_path, check_date, strategy) DO UPDATE
                SET lcp = EXCLUDED.lcp,
                    fid = EXCLUDED.fid,
                    cls = EXCLUDED.cls,
                    fcp = EXCLUDED.fcp,
                    inp = EXCLUDED.inp,
                    ttfb = EXCLUDED.ttfb,
                    tti = EXCLUDED.tti,
                    tbt = EXCLUDED.tbt,
                    speed_index = EXCLUDED.speed_index,
                    performance_score = EXCLUDED.performance_score,
                    accessibility_score = EXCLUDED.accessibility_score,
                    best_practices_score = EXCLUDED.best_practices_score,
                    seo_score = EXCLUDED.seo_score,
                    pwa_score = EXCLUDED.pwa_score,
                    cwv_assessment = EXCLUDED.cwv_assessment,
                    opportunities = EXCLUDED.opportunities,
                    diagnostics = EXCLUDED.diagnostics,
                    lighthouse_version = EXCLUDED.lighthouse_version,
                    user_agent = EXCLUDED.user_agent,
                    fetch_time = CURRENT_TIMESTAMP
            """, (
                property,
                page_path,
                check_date,
                strategy,
                metrics['lcp'],
                metrics['fid'],
                metrics['cls'],
                metrics['fcp'],
                metrics['inp'],
                metrics['ttfb'],
                metrics['tti'],
                metrics['tbt'],
                metrics['speed_index'],
                metrics['performance_score'],
                metrics['accessibility_score'],
                metrics['best_practices_score'],
                metrics['seo_score'],
                metrics['pwa_score'],
                metrics['cwv_assessment'],
                psycopg2.extras.Json(metrics['opportunities']) if metrics['opportunities'] else None,
                psycopg2.extras.Json(metrics['diagnostics']) if metrics['diagnostics'] else None,
                metrics['lighthouse_version'],
                metrics['user_agent']
            ))
            conn.commit()

            print(f"✓ {page_path} ({strategy}): Score={metrics['performance_score']}, LCP={metrics['lcp']:.2f}s, CLS={metrics['cls']:.3f}")

    except Exception as e:
        print(f"✗ Error saving CWV data: {e}")
        conn.rollback()
    finally:
        conn.close()

def main():
    print("=== Core Web Vitals Monitoring ===")
    print(f"Date: {date.today()}\n")

    # Get pages to monitor
    pages = get_monitored_pages()
    print(f"Found {len(pages)} pages to monitor\n")

    for page_id, property, page_path, page_name, check_mobile, check_desktop in pages:
        full_url = f"{property}{page_path}"
        print(f"\nMonitoring: {page_name or page_path} - {full_url}")

        # Check mobile if enabled
        if check_mobile:
            print(f"  → Mobile strategy...")
            result = run_pagespeed_insights(full_url, 'mobile')
            if result:
                metrics = extract_cwv_metrics(result)
                save_cwv_data(page_id, property, page_path, 'mobile', metrics)
            time.sleep(2)  # Delay to avoid rate limiting

        # Check desktop if enabled
        if check_desktop:
            print(f"  → Desktop strategy...")
            result = run_pagespeed_insights(full_url, 'desktop')
            if result:
                metrics = extract_cwv_metrics(result)
                save_cwv_data(page_id, property, page_path, 'desktop', metrics)
            time.sleep(2)  # Delay to avoid rate limiting

    print(f"\n✓ CWV monitoring complete!")

if __name__ == '__main__':
    main()
