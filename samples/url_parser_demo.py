"""
URL Parser Demonstration Script

Shows key functionality of the URLParser class for tracking and normalizing URL variations.
"""
from insights_core.url_parser import URLParser


def main():
    """Demonstrate URL parser functionality"""
    parser = URLParser()

    print("=" * 70)
    print("URL PARSER DEMONSTRATION")
    print("=" * 70)

    # 1. URL Normalization
    print("\n1. URL NORMALIZATION")
    print("-" * 70)
    test_urls = [
        '/page?utm_source=google&utm_medium=cpc&id=123',
        '/Product/Category/?fbclid=abc123&page=2',
        '/search?gclid=xyz&q=shoes&sort=price',
        '/article#section?mc_cid=campaign123',
    ]

    for url in test_urls:
        normalized = parser.normalize(url)
        print(f"Original:   {url}")
        print(f"Normalized: {normalized}")
        print()

    # 2. Variation Detection
    print("\n2. VARIATION DETECTION")
    print("-" * 70)
    test_url = '/Product/Item/?utm_source=google&id=123&sort=desc#reviews'
    variations = parser.extract_variations(test_url)

    print(f"URL: {test_url}")
    print(f"  - Has query params: {variations['has_query']}")
    print(f"  - Query param count: {variations['query_param_count']}")
    print(f"  - Tracking params: {variations['tracking_params']}")
    print(f"  - Semantic params: {variations['semantic_params']}")
    print(f"  - Has fragment: {variations['has_fragment']}")
    print(f"  - Fragment: {variations['fragment']}")
    print(f"  - Has trailing slash: {variations['has_trailing_slash']}")
    print(f"  - Is mixed case: {variations['is_mixed_case']}")

    # 3. Grouping by Canonical
    print("\n\n3. GROUPING URLS BY CANONICAL FORM")
    print("-" * 70)
    url_list = [
        '/page?utm_source=google&id=1',
        '/page?utm_source=facebook&id=1',
        '/Page/?utm_campaign=summer&id=1',
        '/page#section?id=1',
        '/page?id=1',
        '/other?utm_source=twitter',
    ]

    groups = parser.group_by_canonical(url_list)

    for canonical, variations_list in groups.items():
        print(f"\nCanonical: {canonical}")
        print(f"Variations ({len(variations_list)}):")
        for var in variations_list:
            print(f"  - {var}")

    # 4. Variation Type Detection
    print("\n\n4. VARIATION TYPE DETECTION")
    print("-" * 70)
    base = '/page'
    variations_to_test = [
        ('/page?utm_source=google', 'Expected: query_param'),
        ('/page#section', 'Expected: fragment'),
        ('/page/', 'Expected: trailing_slash'),
        ('/Page', 'Expected: case'),
        ('/page', 'Expected: identical'),
    ]

    for variation, expected in variations_to_test:
        var_type = parser.detect_variation_type(base, variation)
        print(f"{variation:30s} -> {var_type:15s} ({expected})")

    # 5. Tracking Parameter Coverage
    print("\n\n5. TRACKING PARAMETER COVERAGE")
    print("-" * 70)
    print(f"Total tracking parameters recognized: {len(parser.TRACKING_PARAMS)}")
    print("\nSample tracking parameters:")
    sample_params = list(parser.TRACKING_PARAMS)[:20]
    for i in range(0, len(sample_params), 5):
        print(f"  {', '.join(sample_params[i:i+5])}")

    print("\n\nSemantic parameters preserved:")
    sample_semantic = list(parser.PRESERVE_PARAMS)[:20]
    for i in range(0, len(sample_semantic), 5):
        print(f"  {', '.join(sample_semantic[i:i+5])}")

    # 6. Real-world Example
    print("\n\n6. REAL-WORLD EXAMPLE")
    print("-" * 70)
    print("E-commerce product page with various tracking:")

    product_urls = [
        'https://example.com/Products/Shoes/Running-Shoes?id=123&color=blue&size=10&utm_source=google&utm_medium=cpc&utm_campaign=summer-sale&gclid=abc123',
        'https://example.com/products/shoes/running-shoes/?id=123&color=blue&size=10&fbclid=xyz789&fb_source=instagram',
        'HTTPS://EXAMPLE.COM/Products/Shoes/Running-Shoes?id=123&color=blue&size=10#reviews',
        'https://example.com/products/shoes/running-shoes?id=123&color=blue&size=10',
    ]

    print("\nAll variations would normalize to:")
    # For demo, just show the path normalization
    for url in product_urls:
        # Extract just the path and query for demo
        from urllib.parse import urlparse
        parsed = urlparse(url)
        relative_url = parsed.path + ('?' + parsed.query if parsed.query else '') + ('#' + parsed.fragment if parsed.fragment else '')
        normalized = parser.normalize(relative_url)
        print(f"  {normalized}")

    print("\n" + "=" * 70)
    print("DEMONSTRATION COMPLETE")
    print("=" * 70)


if __name__ == '__main__':
    main()
