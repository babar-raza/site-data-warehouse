"""Test GA4 API connection and credentials."""
import sys
import os
import io

# Fix encoding for Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from google.analytics.data_v1beta import BetaAnalyticsDataClient
    from google.analytics.data_v1beta.types import (
        RunReportRequest, DateRange, Dimension, Metric
    )
    from datetime import datetime, timedelta

    # Configuration
    CREDENTIALS_FILE = 'secrets/gsc_sa.json'
    PROPERTY_ID = '475105521'

    print("=" * 60)
    print("GA4 API Connection Test")
    print("=" * 60)
    print(f"Credentials file: {CREDENTIALS_FILE}")
    print(f"Property ID: {PROPERTY_ID}")
    print()

    # Check credentials file exists
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[FAIL] Credentials file not found at {CREDENTIALS_FILE}")
        sys.exit(1)

    print(f"[OK] Credentials file exists")

    # Initialize client
    try:
        client = BetaAnalyticsDataClient.from_service_account_json(CREDENTIALS_FILE)
        print(f"[OK] GA4 client initialized successfully")
    except Exception as e:
        print(f"[FAIL] Failed to initialize GA4 client")
        print(f"   Error: {e}")
        sys.exit(1)

    # Test query (last 7 days)
    end_date = datetime.now().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)

    print(f"\nTesting API query...")
    print(f"  Date range: {start_date} to {end_date}")

    try:
        request = RunReportRequest(
            property=f"properties/{PROPERTY_ID}",
            dimensions=[
                Dimension(name="date"),
                Dimension(name="pagePath")
            ],
            metrics=[
                Metric(name="sessions"),
                Metric(name="conversions")
            ],
            date_ranges=[DateRange(
                start_date=start_date.strftime("%Y-%m-%d"),
                end_date=end_date.strftime("%Y-%m-%d")
            )],
            limit=10
        )

        response = client.run_report(request)

        print(f"\n[SUCCESS] GA4 API Connection Successful!")
        print(f"   Rows returned: {len(response.rows)}")

        if len(response.rows) > 0:
            print(f"\n   Sample data (first 3 rows):")
            for i, row in enumerate(response.rows[:3]):
                date_val = row.dimension_values[0].value
                page_val = row.dimension_values[1].value
                sessions = row.metric_values[0].value
                conversions = row.metric_values[1].value
                print(f"     {i+1}. {date_val} | {page_val[:50]:<50} | Sessions: {sessions:>5} | Conv: {conversions:>3}")

        print("\n" + "=" * 60)
        print("Test Result: PASS")
        print("=" * 60)
        print("\nNext steps:")
        print("  1. Verify service account has 'Viewer' role on GA4 property")
        print("  2. Proceed to Phase 3: Deploy GA4 Ingestor Service")

        sys.exit(0)

    except Exception as e:
        print(f"\n[FAIL] GA4 API Connection Failed")
        print(f"   Error: {e}")
        print(f"\nTroubleshooting:")
        print(f"  1. Check service account has 'Viewer' role on GA4 property {PROPERTY_ID}")
        print(f"  2. Verify Analytics Data API is enabled in GCP Console")
        print(f"  3. Confirm credentials file is correct")
        print(f"  4. Check if property ID {PROPERTY_ID} is correct")
        sys.exit(1)

except ImportError as e:
    print(f"[FAIL] Missing required library")
    print(f"   Error: {e}")
    print(f"\nPlease install:")
    print(f"  pip install google-analytics-data")
    sys.exit(1)
