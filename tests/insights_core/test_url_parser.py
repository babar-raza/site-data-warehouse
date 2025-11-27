"""
Tests for URL Parser

Comprehensive test suite covering:
- URL normalization (tracking params, case, trailing slashes)
- Variation extraction and detection
- Grouping and consolidation
- Database operations (with mocks)
- Edge cases and error handling
"""
import pytest
from unittest.mock import Mock, patch, MagicMock, call
from insights_core.url_parser import URLParser


class TestURLParser:
    """Test suite for URLParser core functionality"""

    @pytest.fixture
    def parser(self):
        """Create parser instance without database"""
        return URLParser()

    # ========================================
    # Test normalize() - Tracking Parameters
    # ========================================

    def test_normalize_removes_utm_params(self, parser):
        """Test that UTM parameters are removed"""
        url = '/page?utm_source=google&utm_medium=cpc&id=123'
        result = parser.normalize(url)
        assert 'utm_source' not in result
        assert 'utm_medium' not in result
        assert 'id=123' in result

    def test_normalize_removes_all_utm_variants(self, parser):
        """Test removal of all UTM parameter variants"""
        url = '/page?utm_campaign=summer&utm_term=shoes&utm_content=banner&id=1'
        result = parser.normalize(url)
        assert 'utm_campaign' not in result
        assert 'utm_term' not in result
        assert 'utm_content' not in result
        assert 'id=1' in result

    def test_normalize_removes_facebook_params(self, parser):
        """Test that Facebook tracking params are removed"""
        url = '/page?fbclid=abc123&id=456'
        result = parser.normalize(url)
        assert 'fbclid' not in result
        assert 'id=456' in result

    def test_normalize_removes_facebook_ad_params(self, parser):
        """Test removal of Facebook advertising parameters"""
        url = '/page?fbadid=123&fbadsetid=456&fbcampaignid=789&category=test'
        result = parser.normalize(url)
        assert 'fbadid' not in result
        assert 'fbadsetid' not in result
        assert 'fbcampaignid' not in result
        assert 'category=test' in result

    def test_normalize_removes_google_params(self, parser):
        """Test that Google tracking params are removed"""
        url = '/page?gclid=xyz&gclsrc=aw.ds&category=test'
        result = parser.normalize(url)
        assert 'gclid' not in result
        assert 'gclsrc' not in result
        assert 'category=test' in result

    def test_normalize_removes_google_analytics_params(self, parser):
        """Test removal of Google Analytics client-side parameters"""
        url = '/page?_ga=GA1.2.123456&_gl=1*abc*_gcl_au*def&page=2'
        result = parser.normalize(url)
        assert '_ga' not in result
        assert '_gl' not in result
        assert 'page=2' in result

    def test_normalize_removes_microsoft_params(self, parser):
        """Test removal of Microsoft/Bing tracking parameters"""
        url = '/page?msclkid=abc123&mstoken=def456&id=789'
        result = parser.normalize(url)
        assert 'msclkid' not in result
        assert 'mstoken' not in result
        assert 'id=789' in result

    def test_normalize_removes_mailchimp_params(self, parser):
        """Test removal of Mailchimp tracking parameters"""
        url = '/page?mc_cid=campaign123&mc_eid=email456&product=test'
        result = parser.normalize(url)
        assert 'mc_cid' not in result
        assert 'mc_eid' not in result
        assert 'product=test' in result

    def test_normalize_removes_common_tracking_params(self, parser):
        """Test removal of common tracking parameters"""
        url = '/page?ref=homepage&source=newsletter&affiliate=partner1&id=123'
        result = parser.normalize(url)
        assert 'ref' not in result
        assert 'source' not in result
        assert 'affiliate' not in result
        assert 'id=123' in result

    def test_normalize_removes_session_params(self, parser):
        """Test removal of session/state parameters"""
        url = '/page?sessionid=abc&sid=def&token=ghi&page=2'
        result = parser.normalize(url)
        assert 'sessionid' not in result
        assert 'sid' not in result
        assert 'token' not in result
        assert 'page=2' in result

    # ========================================
    # Test normalize() - Path Normalization
    # ========================================

    def test_normalize_handles_trailing_slashes(self, parser):
        """Test trailing slash normalization"""
        assert parser.normalize('/page/') == '/page'
        assert parser.normalize('/') == '/'
        assert parser.normalize('/page') == '/page'

    def test_normalize_handles_multiple_trailing_slashes(self, parser):
        """Test multiple trailing slashes are normalized"""
        assert parser.normalize('/page///') == '/page'

    def test_normalize_lowercases_path(self, parser):
        """Test path case normalization"""
        assert parser.normalize('/Page/SubPage') == '/page/subpage'
        assert parser.normalize('/PRODUCTS/Item') == '/products/item'

    def test_normalize_preserves_path_structure(self, parser):
        """Test that path structure is preserved"""
        assert parser.normalize('/category/subcategory/item') == '/category/subcategory/item'

    # ========================================
    # Test normalize() - Fragment Handling
    # ========================================

    def test_normalize_removes_fragments_by_default(self, parser):
        """Test fragment removal"""
        url = '/page#section'
        result = parser.normalize(url)
        assert '#' not in result
        assert 'section' not in result

    def test_normalize_preserves_fragments_when_requested(self, parser):
        """Test fragment preservation option"""
        url = '/page#section'
        result = parser.normalize(url, remove_fragment=False)
        assert '#section' in result

    def test_normalize_handles_complex_fragments(self, parser):
        """Test handling of complex fragments"""
        url = '/page#section-1.2.3'
        result = parser.normalize(url, remove_fragment=False)
        assert '#section-1.2.3' in result

    # ========================================
    # Test normalize() - Query Parameters
    # ========================================

    def test_normalize_sorts_query_params(self, parser):
        """Test that query params are sorted alphabetically"""
        url = '/page?z=1&a=2&m=3'
        result = parser.normalize(url)
        # Should be alphabetically sorted
        assert result.index('a=') < result.index('m=') < result.index('z=')

    def test_normalize_preserves_semantic_params(self, parser):
        """Test that semantic params are preserved"""
        url = '/search?q=test&utm_source=google'
        result = parser.normalize(url)
        assert 'q=test' in result
        assert 'utm_source' not in result

    def test_normalize_preserves_all_semantic_params(self, parser):
        """Test preservation of various semantic parameters"""
        url = '/page?sort=desc&filter=active&page=2&utm_campaign=test'
        result = parser.normalize(url)
        assert 'sort=desc' in result
        assert 'filter=active' in result
        assert 'page=2' in result
        assert 'utm_campaign' not in result

    def test_normalize_handles_multiple_param_values(self, parser):
        """Test handling of parameters with multiple values"""
        url = '/page?filter=cat1&filter=cat2&utm_source=test'
        result = parser.normalize(url)
        assert 'filter=cat1' in result
        assert 'filter=cat2' in result
        assert 'utm_source' not in result

    def test_normalize_lowercases_param_keys(self, parser):
        """Test that parameter keys are lowercased"""
        url = '/page?ID=123&Page=2'
        result = parser.normalize(url)
        assert 'id=123' in result
        assert 'page=2' in result
        # Check that uppercase versions are not present
        assert 'ID=' not in result
        assert 'Page=' not in result

    # ========================================
    # Test normalize() - Edge Cases
    # ========================================

    def test_normalize_empty_url(self, parser):
        """Test handling of empty URL"""
        assert parser.normalize('') == ''
        assert parser.normalize(None) == ''

    def test_normalize_root_url(self, parser):
        """Test normalization of root URL"""
        assert parser.normalize('/') == '/'
        assert parser.normalize('/?utm_source=test') == '/'

    def test_normalize_url_with_only_query_params(self, parser):
        """Test URL that is only query parameters"""
        result = parser.normalize('?id=123&utm_source=test')
        assert 'id=123' in result
        assert 'utm_source' not in result

    def test_normalize_url_with_special_characters(self, parser):
        """Test handling of special characters in URLs"""
        url = '/page?q=hello%20world&id=123'
        result = parser.normalize(url)
        assert 'id=123' in result

    def test_normalize_preserves_encoded_characters(self, parser):
        """Test that URL encoding is preserved"""
        url = '/search?q=foo%2Bbar&id=1'
        result = parser.normalize(url)
        assert 'q=foo%2Bbar' in result or 'q=foo+bar' in result

    def test_handles_malformed_urls(self, parser):
        """Test handling of malformed URLs"""
        # Should not raise exception
        result = parser.normalize('not a url at all')
        assert result is not None

    # ========================================
    # Test extract_variations()
    # ========================================

    def test_extract_variations_identifies_tracking_params(self, parser):
        """Test tracking param identification"""
        url = '/page?utm_source=google&id=123'
        result = parser.extract_variations(url)
        assert 'utm_source' in result['tracking_params']
        assert result['tracking_param_count'] == 1

    def test_extract_variations_counts_multiple_tracking_params(self, parser):
        """Test counting multiple tracking parameters"""
        url = '/page?utm_source=google&utm_medium=cpc&fbclid=abc&gclid=xyz'
        result = parser.extract_variations(url)
        assert result['tracking_param_count'] == 4

    def test_extract_variations_identifies_semantic_params(self, parser):
        """Test semantic param identification"""
        url = '/page?q=search&sort=desc&page=2'
        result = parser.extract_variations(url)
        assert 'q' in result['semantic_params']
        assert 'sort' in result['semantic_params']
        assert 'page' in result['semantic_params']
        assert result['semantic_param_count'] == 3

    def test_extract_variations_identifies_fragments(self, parser):
        """Test fragment identification"""
        url = '/page#section'
        result = parser.extract_variations(url)
        assert result['has_fragment'] is True
        assert result['fragment'] == 'section'

    def test_extract_variations_handles_no_fragment(self, parser):
        """Test handling of URLs without fragments"""
        url = '/page'
        result = parser.extract_variations(url)
        assert result['has_fragment'] is False
        assert result['fragment'] is None

    def test_extract_variations_identifies_trailing_slash(self, parser):
        """Test trailing slash identification"""
        url = '/page/'
        result = parser.extract_variations(url)
        assert result['has_trailing_slash'] is True

    def test_extract_variations_no_trailing_slash_on_root(self, parser):
        """Test that root path doesn't count as trailing slash"""
        url = '/'
        result = parser.extract_variations(url)
        assert result['has_trailing_slash'] is False

    def test_extract_variations_identifies_mixed_case(self, parser):
        """Test mixed case identification"""
        url = '/Page/SubPage'
        result = parser.extract_variations(url)
        assert result['is_mixed_case'] is True

    def test_extract_variations_lowercase_not_mixed(self, parser):
        """Test that lowercase paths are not considered mixed case"""
        url = '/page/subpage'
        result = parser.extract_variations(url)
        assert result['is_mixed_case'] is False

    def test_extract_variations_has_query_flag(self, parser):
        """Test has_query flag"""
        url = '/page?id=123'
        result = parser.extract_variations(url)
        assert result['has_query'] is True
        assert result['query_param_count'] > 0

    def test_extract_variations_no_query(self, parser):
        """Test URLs without query parameters"""
        url = '/page'
        result = parser.extract_variations(url)
        assert result['has_query'] is False
        assert result['query_param_count'] == 0

    def test_extract_variations_handles_empty_url(self, parser):
        """Test empty URL handling"""
        result = parser.extract_variations('')
        assert 'error' in result

    def test_extract_variations_handles_none(self, parser):
        """Test None URL handling"""
        result = parser.extract_variations(None)
        assert 'error' in result

    def test_extract_variations_returns_original_url(self, parser):
        """Test that original URL is included in results"""
        url = '/page?id=123'
        result = parser.extract_variations(url)
        assert result['original_url'] == url

    def test_extract_variations_returns_path(self, parser):
        """Test that path is extracted"""
        url = '/category/product?id=123'
        result = parser.extract_variations(url)
        assert result['path'] == '/category/product'

    # ========================================
    # Test group_by_canonical()
    # ========================================

    def test_group_by_canonical_groups_correctly(self, parser):
        """Test URL grouping"""
        urls = [
            '/page?utm_source=google',
            '/page?utm_source=facebook',
            '/page',
            '/other'
        ]
        groups = parser.group_by_canonical(urls)

        assert '/page' in groups
        assert len(groups['/page']) == 3
        assert '/other' in groups
        assert len(groups['/other']) == 1

    def test_group_by_canonical_handles_empty_list(self, parser):
        """Test empty list handling"""
        groups = parser.group_by_canonical([])
        assert groups == {}

    def test_group_by_canonical_no_duplicates(self, parser):
        """Test that same URL doesn't appear multiple times"""
        urls = ['/page', '/page', '/page']
        groups = parser.group_by_canonical(urls)
        assert len(groups['/page']) == 1

    def test_group_by_canonical_handles_none_in_list(self, parser):
        """Test handling of None values in list"""
        urls = ['/page', None, '/other', '']
        groups = parser.group_by_canonical(urls)
        assert '/page' in groups
        assert '/other' in groups
        # None and empty string should be skipped
        assert len(groups) == 2

    def test_group_by_canonical_complex_variations(self, parser):
        """Test grouping with complex variations"""
        urls = [
            '/page?utm_source=google&id=1',
            '/Page/?utm_campaign=summer',
            '/page#section',
            '/page/',
            '/page',
        ]
        groups = parser.group_by_canonical(urls)

        # URLs without semantic params should group to '/page'
        # URL with id=1 should group to '/page?id=1'
        assert '/page' in groups or '/page?id=1' in groups
        # Should have at least 4 variations in the main group
        total_variations = sum(len(v) for v in groups.values())
        assert total_variations == 5

    def test_group_by_canonical_preserves_original_urls(self, parser):
        """Test that original URLs are preserved in groups"""
        urls = [
            '/page?utm_source=google',
            '/page?utm_source=facebook',
        ]
        groups = parser.group_by_canonical(urls)

        assert '/page?utm_source=google' in groups['/page']
        assert '/page?utm_source=facebook' in groups['/page']

    # ========================================
    # Test detect_variation_type()
    # ========================================

    def test_detect_variation_type_query_param(self, parser):
        """Test query param variation detection"""
        result = parser.detect_variation_type('/page', '/page?utm_source=google')
        assert result == 'query_param'

    def test_detect_variation_type_fragment(self, parser):
        """Test fragment variation detection"""
        result = parser.detect_variation_type('/page', '/page#section')
        assert result == 'fragment'

    def test_detect_variation_type_trailing_slash(self, parser):
        """Test trailing slash variation detection"""
        result = parser.detect_variation_type('/page', '/page/')
        assert result == 'trailing_slash'

    def test_detect_variation_type_case(self, parser):
        """Test case variation detection"""
        result = parser.detect_variation_type('/page', '/Page')
        assert result == 'case'

    def test_detect_variation_type_identical(self, parser):
        """Test identical URLs"""
        result = parser.detect_variation_type('/page', '/page')
        assert result == 'identical'

    def test_detect_variation_type_priority_query_param(self, parser):
        """Test that query_param takes priority over other types"""
        # Has both tracking param and fragment
        result = parser.detect_variation_type('/page', '/page?utm_source=test#section')
        assert result == 'query_param'

    def test_detect_variation_type_priority_fragment(self, parser):
        """Test that fragment takes priority over trailing slash"""
        # Has both fragment and trailing slash
        result = parser.detect_variation_type('/page', '/page/#section')
        assert result == 'fragment'

    def test_detect_variation_type_other(self, parser):
        """Test 'other' type for unclassified variations"""
        # Two completely different paths
        result = parser.detect_variation_type('/page1', '/page2')
        assert result == 'other'

    # ========================================
    # Test Edge Cases and Error Handling
    # ========================================

    def test_handles_unicode_characters(self, parser):
        """Test handling of unicode characters"""
        url = '/page?q=\u4e2d\u6587&id=123'
        result = parser.normalize(url)
        assert 'id=123' in result

    def test_handles_very_long_urls(self, parser):
        """Test handling of very long URLs"""
        long_query = '&'.join([f'param{i}=value{i}' for i in range(100)])
        url = f'/page?{long_query}&utm_source=test'
        result = parser.normalize(url)
        # Should not crash
        assert result is not None
        assert 'utm_source' not in result

    def test_handles_empty_query_values(self, parser):
        """Test handling of empty query parameter values"""
        url = '/page?id=&name='
        result = parser.normalize(url)
        # Should handle gracefully
        assert result is not None

    def test_handles_duplicate_params(self, parser):
        """Test handling of duplicate parameter names"""
        url = '/page?id=123&id=456&utm_source=test'
        result = parser.normalize(url)
        assert 'id=123' in result or 'id=456' in result
        assert 'utm_source' not in result


class TestURLParserDatabase:
    """Test database operations (with mocks)"""

    @pytest.fixture
    def parser_with_db(self):
        """Create parser with mock DSN"""
        return URLParser(db_dsn='postgresql://test:test@localhost:5432/test_db')

    @patch('psycopg2.connect')
    def test_store_variation_success(self, mock_connect, parser_with_db):
        """Test successful variation storage"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        result = parser_with_db.store_variation(
            'sc-domain:example.com',
            '/page',
            '/page?utm_source=google'
        )

        assert result is True
        mock_cursor.execute.assert_called_once()
        mock_conn.commit.assert_called_once()
        mock_cursor.close.assert_called_once()
        mock_conn.close.assert_called_once()

    @patch('psycopg2.connect')
    def test_store_variation_handles_error(self, mock_connect, parser_with_db):
        """Test error handling in variation storage"""
        mock_connect.side_effect = Exception("Connection failed")

        result = parser_with_db.store_variation(
            'sc-domain:example.com',
            '/page',
            '/page?utm_source=google'
        )

        assert result is False

    @patch('psycopg2.connect')
    def test_store_variation_skips_identical(self, mock_connect, parser_with_db):
        """Test that identical URLs are skipped"""
        result = parser_with_db.store_variation(
            'sc-domain:example.com',
            '/page',
            '/page'
        )

        # Should return True but not connect to DB
        assert result is True
        mock_connect.assert_not_called()

    @patch('psycopg2.connect')
    def test_store_variation_rollback_on_error(self, mock_connect, parser_with_db):
        """Test that transaction is rolled back on error"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.execute.side_effect = Exception("Database error")

        result = parser_with_db.store_variation(
            'sc-domain:example.com',
            '/page',
            '/page?utm_source=google'
        )

        assert result is False
        mock_conn.rollback.assert_called_once()

    @patch('psycopg2.connect')
    def test_detect_consolidation_opportunities_success(self, mock_connect, parser_with_db):
        """Test consolidation opportunity detection"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock database response
        from datetime import datetime
        mock_cursor.fetchall.return_value = [
            {
                'canonical_url': '/page',
                'variation_count': 5,
                'variation_types': ['query_param', 'trailing_slash'],
                'total_occurrences': 100,
                'first_seen': datetime(2025, 1, 1),
                'last_seen': datetime(2025, 11, 26),
            }
        ]

        result = parser_with_db.detect_consolidation_opportunities('sc-domain:example.com')

        assert len(result) == 1
        assert result[0]['canonical_url'] == '/page'
        assert result[0]['variation_count'] == 5
        assert 'recommendation' in result[0]
        assert 'canonical tags' in result[0]['recommendation'].lower()

    @patch('psycopg2.connect')
    def test_detect_consolidation_opportunities_empty(self, mock_connect, parser_with_db):
        """Test consolidation detection with no results"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        mock_cursor.fetchall.return_value = []

        result = parser_with_db.detect_consolidation_opportunities('sc-domain:example.com')

        assert len(result) == 0

    @patch('psycopg2.connect')
    def test_detect_consolidation_opportunities_error(self, mock_connect, parser_with_db):
        """Test error handling in consolidation detection"""
        mock_connect.side_effect = Exception("Database error")

        result = parser_with_db.detect_consolidation_opportunities('sc-domain:example.com')

        assert result == []

    def test_detect_consolidation_no_dsn(self):
        """Test behavior when no DSN configured"""
        parser = URLParser(db_dsn=None)
        # Clear any env var
        import os
        original = os.environ.get('WAREHOUSE_DSN')
        if 'WAREHOUSE_DSN' in os.environ:
            del os.environ['WAREHOUSE_DSN']

        try:
            result = parser.detect_consolidation_opportunities('sc-domain:example.com')
            assert result == []
        finally:
            if original:
                os.environ['WAREHOUSE_DSN'] = original

    @patch('psycopg2.connect')
    def test_batch_store_variations_success(self, mock_connect, parser_with_db):
        """Test batch storing variations"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        url_pairs = [
            ('/page', '/page?utm_source=google'),
            ('/page', '/page?utm_source=facebook'),
            ('/other', '/other#section'),
        ]

        result = parser_with_db.batch_store_variations('sc-domain:example.com', url_pairs)

        assert result == 3
        assert mock_cursor.execute.call_count == 3
        mock_conn.commit.assert_called_once()

    @patch('psycopg2.connect')
    def test_batch_store_variations_skips_identical(self, mock_connect, parser_with_db):
        """Test that batch store skips identical URLs"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        url_pairs = [
            ('/page', '/page'),  # Identical, should be skipped
            ('/page', '/page?utm_source=google'),
        ]

        result = parser_with_db.batch_store_variations('sc-domain:example.com', url_pairs)

        assert result == 1
        assert mock_cursor.execute.call_count == 1

    @patch('psycopg2.connect')
    def test_batch_store_variations_handles_error(self, mock_connect, parser_with_db):
        """Test error handling in batch store"""
        mock_connect.side_effect = Exception("Connection failed")

        url_pairs = [
            ('/page', '/page?utm_source=google'),
        ]

        result = parser_with_db.batch_store_variations('sc-domain:example.com', url_pairs)

        assert result == 0

    def test_batch_store_variations_no_dsn(self):
        """Test batch store with no DSN"""
        parser = URLParser(db_dsn=None)

        url_pairs = [
            ('/page', '/page?utm_source=google'),
        ]

        result = parser.batch_store_variations('sc-domain:example.com', url_pairs)
        assert result == 0


class TestURLParserRecommendations:
    """Test recommendation generation logic"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return URLParser()

    def test_generate_recommendation_query_param(self, parser):
        """Test recommendation for query param variations"""
        opportunity = {
            'variation_types': ['query_param'],
            'variation_count': 5,
            'total_occurrences': 100
        }
        result = parser._generate_recommendation(opportunity)
        assert 'canonical tags' in result.lower()
        assert '301 redirects' in result.lower()
        assert '5' in result

    def test_generate_recommendation_trailing_slash(self, parser):
        """Test recommendation for trailing slash variations"""
        opportunity = {
            'variation_types': ['trailing_slash'],
            'variation_count': 3,
            'total_occurrences': 50
        }
        result = parser._generate_recommendation(opportunity)
        assert 'trailing slash' in result.lower()
        assert 'standardize' in result.lower()
        assert '3' in result

    def test_generate_recommendation_case(self, parser):
        """Test recommendation for case variations"""
        opportunity = {
            'variation_types': ['case'],
            'variation_count': 2,
            'total_occurrences': 30
        }
        result = parser._generate_recommendation(opportunity)
        assert 'case' in result.lower()
        assert 'normalize' in result.lower()
        assert '2' in result

    def test_generate_recommendation_fragment(self, parser):
        """Test recommendation for fragment variations"""
        opportunity = {
            'variation_types': ['fragment'],
            'variation_count': 4,
            'total_occurrences': 80
        }
        result = parser._generate_recommendation(opportunity)
        assert 'fragment' in result.lower()
        assert '4' in result

    def test_generate_recommendation_protocol(self, parser):
        """Test recommendation for protocol variations"""
        opportunity = {
            'variation_types': ['protocol'],
            'variation_count': 2,
            'total_occurrences': 200
        }
        result = parser._generate_recommendation(opportunity)
        assert 'https' in result.lower() or 'protocol' in result.lower()
        assert '2' in result

    def test_generate_recommendation_other(self, parser):
        """Test recommendation for other variations"""
        opportunity = {
            'variation_types': ['other'],
            'variation_count': 3,
            'total_occurrences': 40
        }
        result = parser._generate_recommendation(opportunity)
        assert 'review' in result.lower()
        assert '3' in result


class TestURLParserIntegration:
    """Integration tests combining multiple operations"""

    @pytest.fixture
    def parser(self):
        """Create parser instance"""
        return URLParser()

    def test_full_workflow_normalization_and_grouping(self, parser):
        """Test complete workflow of normalizing and grouping URLs"""
        urls = [
            '/Product/Item?utm_source=google&id=123',
            '/product/item/?utm_campaign=summer&id=123',
            '/product/item#reviews?id=123',
            '/product/item?id=123&page=1',
        ]

        # Group by canonical
        groups = parser.group_by_canonical(urls)

        # URLs with same semantic params should group together
        # id=123 and id=123&page=1 will be different groups due to different params
        # But all should be normalized versions of /product/item
        for canonical in groups.keys():
            assert canonical.startswith('/product/item')
            assert canonical.islower()
            assert 'utm_source' not in canonical
            assert 'utm_campaign' not in canonical

        # Total variations should match input
        total_variations = sum(len(v) for v in groups.values())
        assert total_variations == 4

    def test_variation_detection_and_classification(self, parser):
        """Test detecting and classifying multiple variations"""
        base_url = '/page'
        variations = [
            ('/page?utm_source=google', 'query_param'),
            ('/page#section', 'fragment'),
            ('/page/', 'trailing_slash'),
            ('/Page', 'case'),
        ]

        for variation, expected_type in variations:
            detected_type = parser.detect_variation_type(base_url, variation)
            assert detected_type == expected_type

    def test_extract_and_classify_complex_url(self, parser):
        """Test extraction and classification of complex URL"""
        url = '/Product/Item/?utm_source=google&id=123&sort=desc#reviews'

        # Extract variations
        info = parser.extract_variations(url)

        assert info['has_query'] is True
        assert info['has_fragment'] is True
        assert info['has_trailing_slash'] is True
        assert info['is_mixed_case'] is True
        assert info['tracking_param_count'] == 1
        assert 'id' in info['semantic_params']

        # Normalize
        normalized = parser.normalize(url)

        assert 'utm_source' not in normalized
        assert normalized.islower()
        assert not normalized.endswith('/')
        assert '#' not in normalized
