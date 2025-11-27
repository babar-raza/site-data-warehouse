#!/usr/bin/env python3
"""
Test SerpStack API Key
======================
Tests your SerpStack API key and shows example results
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from insights_core.serp_tracker import SerpStackProvider
import httpx


async def test_serpstack_api(api_key: str):
    """Test SerpStack API key"""

    print("=" * 70)
    print("SerpStack API Key Test")
    print("=" * 70)
    print()
    print(f"API Key: {api_key[:10]}...{api_key[-10:]}")
    print()

    # Test 1: Perform a test search (validates API key)
    print("Test 1: Performing test search (validates API key)...")
    print("-" * 70)
    print("Query: 'python programming'")
    print()

    result = None
    try:
        provider = SerpStackProvider(api_key)

        result = await provider.search(
            query='python programming',
            location='United States',
            device='desktop',
            num_results=10
        )

        print("[OK] Search successful!")
        print("[OK] API Key is VALID!")
        print()
        print(f"Total Results: {result.get('total_results', 'N/A'):,}")
        print()
        print("NOTE: SerpStack free plan = 100 requests/month")
        print("      This test used 1 request. You have ~99 remaining.")
        print()

        # Show top 10 organic results
        print("Top 10 Organic Results:")
        print()

        for i, res in enumerate(result['organic_results'][:10], 1):
            print(f"{i}. {res['title']}")
            print(f"   {res['url']}")
            print(f"   {res['description'][:100]}...")
            print()

        # Show SERP features
        serp_features = result.get('serp_features', {})
        if serp_features:
            print("SERP Features Detected:")
            for feature, present in serp_features.items():
                if present and not feature.endswith('_data') and not feature.endswith('_questions'):
                    print(f"  [+] {feature.replace('_', ' ').title()}")
            print()

    except Exception as e:
        print(f"[ERROR] Search failed: {e}")
        print()
        import traceback
        traceback.print_exc()
        return False

    # Test 2: Test position tracking for a domain
    print("\nTest 2: Testing position tracking...")
    print("-" * 70)
    print("Searching for 'python.org' in results for 'python programming'")
    print()

    try:
        target_domain = 'python.org'
        position = None

        for i, res in enumerate(result['organic_results'], 1):
            if target_domain in res['url']:
                position = i
                print(f"[OK] Found {target_domain} at position #{position}!")
                print(f"   URL: {res['url']}")
                print(f"   Title: {res['title']}")
                break

        if not position:
            print(f"[INFO] {target_domain} not found in top {len(result['organic_results'])} results")

        print()

    except Exception as e:
        print(f"[ERROR] Position tracking test failed: {e}")

    # Summary
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    print()
    print("[OK] API Key is working correctly!")
    print("[OK] SerpStack integration is ready to use")
    print()
    print("Recommended Configuration:")
    print("  - Primary: GSC data (free, unlimited)")
    print("  - Backup: SerpStack API (100 requests/month)")
    print("  - Strategy: Use API only for high-priority keywords or gaps")
    print()
    print("Next Steps:")
    print("1. Add API key to .env file:")
    print(f"   SERPSTACK_API_KEY={api_key}")
    print("   SERP_API_PROVIDER=serpstack")
    print()
    print("2. Configure hybrid mode (already set up!)")
    print()
    print("3. Run GSC sync for primary tracking:")
    print("   python scripts/sync_gsc_to_serp.py")
    print()
    print("=" * 70)

    return True


async def main():
    """Main test function"""

    # Get API key from command line or prompt
    if len(sys.argv) > 1:
        api_key = sys.argv[1]
    else:
        api_key = "4ee96de5a2308b4d53371470a3717636"  # Your API key

    success = await test_serpstack_api(api_key)

    if success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
