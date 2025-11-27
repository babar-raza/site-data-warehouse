"""
Tests for DiagnosisDetector CSE Integration

Tests the integration of GoogleCSEAnalyzer with DiagnosisDetector
to ensure SERP-based diagnosis and competitor analysis work correctly.
"""
import pytest
from datetime import date, datetime, timedelta
from unittest.mock import Mock, patch, MagicMock, PropertyMock

from insights_core.detectors.diagnosis import DiagnosisDetector, CSE_MIN_QUOTA_THRESHOLD
from insights_core.models import (
    InsightCreate,
    InsightCategory,
    InsightSeverity,
    InsightStatus,
    EntityType,
    InsightMetrics,
)


class TestDiagnosisCseIntegration:
    """Test CSE integration in DiagnosisDetector"""

    @pytest.fixture
    def mock_repository(self):
        """Mock InsightRepository"""
        repo = Mock()
        repo.create = Mock(return_value=Mock(id=1))
        repo.update = Mock()
        repo.get_by_status = Mock(return_value=[])
        return repo

    @pytest.fixture
    def mock_config(self):
        """Mock InsightsConfig"""
        config = Mock()
        config.warehouse_dsn = "postgresql://test:test@localhost/test"
        return config

    @pytest.fixture
    def mock_cse_analyzer(self):
        """Mock GoogleCSEAnalyzer"""
        cse = Mock()
        cse.get_quota_status = Mock(return_value={
            'daily_quota': 100,
            'queries_today': 10,
            'remaining': 90,
            'reset_date': date.today().isoformat()
        })
        cse.analyze_serp = Mock(return_value={
            'query': 'python tutorial',
            'target_domain': 'example.com',
            'target_position': 5,
            'target_result': {
                'position': 5,
                'title': 'Example Tutorial',
                'link': 'https://example.com/tutorial',
                'domain': 'example.com'
            },
            'competitors': [
                {
                    'domain': 'competitor1.com',
                    'position': 1,
                    'title': 'Competitor 1',
                    'link': 'https://competitor1.com',
                    'has_rich_snippet': True
                },
                {
                    'domain': 'competitor2.com',
                    'position': 2,
                    'title': 'Competitor 2',
                    'link': 'https://competitor2.com',
                    'has_rich_snippet': False
                },
                {
                    'domain': 'competitor3.com',
                    'position': 3,
                    'title': 'Competitor 3',
                    'link': 'https://competitor3.com',
                    'has_rich_snippet': True
                }
            ],
            'serp_features': ['rich_snippets', 'thumbnails'],
            'total_results': 10,
            'analyzed_at': datetime.utcnow().isoformat(),
            'domain_distribution': {
                'example.com': 1,
                'competitor1.com': 1,
                'competitor2.com': 1,
                'competitor3.com': 1
            }
        })
        return cse

    def test_cse_optional_loading(self, mock_repository, mock_config):
        """Test that CSE is loaded lazily and optionally"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.GoogleCSEAnalyzer') as mock_cse_class:
                detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)

                # CSE should not be initialized yet
                assert detector._cse_analyzer is None
                assert detector.use_cse is True

                # Access property should trigger lazy loading
                mock_cse_class.return_value = Mock()
                analyzer = detector.cse_analyzer

                # Now it should be initialized
                assert analyzer is not None
                mock_cse_class.assert_called_once()

    def test_cse_disabled_when_flag_false(self, mock_repository, mock_config):
        """Test that CSE is not loaded when use_cse=False"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=False)

            assert detector.use_cse is False
            assert detector.cse_analyzer is None

    def test_graceful_degradation_without_cse(self, mock_repository, mock_config):
        """Test diagnosis works without CSE"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', False):
            detector = DiagnosisDetector(mock_repository, mock_config)

            # Should initialize without CSE
            assert detector.use_cse is False
            assert detector.cse_analyzer is None

            # _get_serp_context should return None gracefully
            result = detector._get_serp_context('sc-domain:example.com', 'test query')
            assert result is None

    def test_cse_initialization_failure_graceful(self, mock_repository, mock_config):
        """Test graceful handling when CSE initialization fails"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.GoogleCSEAnalyzer') as mock_cse_class:
                # Make CSE initialization raise exception
                mock_cse_class.side_effect = Exception("API key missing")

                detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)

                # Try to access CSE analyzer
                analyzer = detector.cse_analyzer

                # Should gracefully handle failure
                assert analyzer is None
                assert detector.use_cse is False

    def test_quota_check_before_cse_call(self, mock_repository, mock_config, mock_cse_analyzer):
        """Test quota is checked before making CSE calls"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse_analyzer

            # Test with sufficient quota
            result = detector._get_serp_context('sc-domain:example.com', 'test query')

            assert result is not None
            mock_cse_analyzer.get_quota_status.assert_called()
            mock_cse_analyzer.analyze_serp.assert_called_once_with('test query', 'example.com')

    def test_quota_too_low_skips_cse(self, mock_repository, mock_config, mock_cse_analyzer):
        """Test CSE is skipped when quota is too low"""
        # Set quota below threshold
        mock_cse_analyzer.get_quota_status.return_value = {
            'daily_quota': 100,
            'queries_today': 97,
            'remaining': 3,  # Below CSE_MIN_QUOTA_THRESHOLD (5)
            'reset_date': date.today().isoformat()
        }

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse_analyzer

            result = detector._get_serp_context('sc-domain:example.com', 'test query')

            # Should skip CSE call
            assert result is None
            mock_cse_analyzer.get_quota_status.assert_called()
            mock_cse_analyzer.analyze_serp.assert_not_called()

    def test_handles_cse_errors(self, mock_repository, mock_config, mock_cse_analyzer):
        """Test graceful handling of CSE errors"""
        # Make analyze_serp raise exception
        mock_cse_analyzer.analyze_serp.side_effect = Exception("API error")

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse_analyzer

            result = detector._get_serp_context('sc-domain:example.com', 'test query')

            # Should return None on error
            assert result is None

    def test_handles_quota_check_errors(self, mock_repository, mock_config, mock_cse_analyzer):
        """Test graceful handling when quota check fails"""
        # Make get_quota_status raise exception
        mock_cse_analyzer.get_quota_status.side_effect = Exception("Quota check failed")

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse_analyzer

            result = detector._get_serp_context('sc-domain:example.com', 'test query')

            # Should return None on quota check error
            assert result is None
            mock_cse_analyzer.analyze_serp.assert_not_called()

    def test_domain_extraction_from_property(self, mock_repository, mock_config, mock_cse_analyzer):
        """Test correct domain extraction from various property formats"""
        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse_analyzer

            # Test different property formats
            test_cases = [
                ('sc-domain:example.com', 'example.com'),
                ('sc-https://example.com', 'example.com'),
                ('sc-https://example.com/', 'example.com'),
                ('sc-http://example.com', 'example.com'),
            ]

            for property_url, expected_domain in test_cases:
                mock_cse_analyzer.analyze_serp.reset_mock()
                detector._get_serp_context(property_url, 'test query')
                mock_cse_analyzer.analyze_serp.assert_called_once_with('test query', expected_domain)


class TestCompetitorInsights:
    """Test competitor analysis insights"""

    @pytest.fixture
    def mock_repository(self):
        """Mock InsightRepository"""
        repo = Mock()
        repo.create = Mock(return_value=Mock(id=1))
        repo.update = Mock()
        return repo

    @pytest.fixture
    def mock_config(self):
        """Mock InsightsConfig"""
        config = Mock()
        config.warehouse_dsn = "postgresql://test:test@localhost/test"
        return config

    @pytest.fixture
    def mock_db_connection(self):
        """Mock database connection"""
        with patch('insights_core.detectors.diagnosis.DiagnosisDetector._get_db_connection') as mock_conn:
            conn = Mock()
            cursor = Mock()
            cursor.__enter__ = Mock(return_value=cursor)
            cursor.__exit__ = Mock(return_value=False)
            cursor.fetchone = Mock(return_value={
                'property': 'sc-domain:example.com',
                'page_path': '/blog/tutorial',
                'date': date.today(),
                'gsc_avg_position': 15.0,
                'gsc_position_change_wow': 12.0,
                'gsc_clicks': 50,
                'gsc_clicks_change_wow': -30,
                'top_query': 'python tutorial',
                'ga_engagement_rate': 0.5,
                'ga_engagement_rate_7d_ago': 0.6,
                'ga_conversions': 5,
                'ga_conversions_change_wow': -2,
                'modified_within_48h': False,
            })
            conn.cursor = Mock(return_value=cursor)
            conn.close = Mock()
            mock_conn.return_value = conn
            yield mock_conn

    @pytest.fixture
    def mock_cse_analyzer(self):
        """Mock GoogleCSEAnalyzer with competitor data"""
        cse = Mock()
        cse.get_quota_status = Mock(return_value={
            'daily_quota': 100,
            'queries_today': 10,
            'remaining': 90,
            'reset_date': date.today().isoformat()
        })
        cse.analyze_serp = Mock(return_value={
            'query': 'python tutorial',
            'target_domain': 'example.com',
            'target_position': 5,
            'competitors': [
                {
                    'domain': 'realpython.com',
                    'position': 1,
                    'title': 'Real Python Tutorial',
                    'link': 'https://realpython.com/tutorial',
                    'has_rich_snippet': True
                },
                {
                    'domain': 'tutorialspoint.com',
                    'position': 2,
                    'title': 'Tutorials Point',
                    'link': 'https://tutorialspoint.com',
                    'has_rich_snippet': True
                },
                {
                    'domain': 'w3schools.com',
                    'position': 3,
                    'title': 'W3Schools',
                    'link': 'https://w3schools.com',
                    'has_rich_snippet': False
                }
            ],
            'serp_features': ['rich_snippets', 'thumbnails', 'breadcrumbs'],
            'total_results': 10,
            'analyzed_at': datetime.utcnow().isoformat()
        })
        return cse

    def test_serp_context_enriches_diagnosis(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test SERP data is added to diagnosis when available"""
        # Create risk insight
        risk = Mock()
        risk.id = "risk-1"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    # Run diagnosis
                    row = mock_db_connection.return_value.cursor.return_value.fetchone.return_value
                    diagnosis = detector._diagnose_risk(risk)

                    # Verify diagnosis was created
                    assert diagnosis is not None
                    assert diagnosis.category == InsightCategory.DIAGNOSIS

                    # Verify SERP context was called
                    mock_cse_analyzer.analyze_serp.assert_called_once_with('python tutorial', 'example.com')

                    # Verify SERP data in metrics
                    metrics_dict = diagnosis.metrics.dict()
                    assert metrics_dict['serp_query'] == 'python tutorial'
                    assert metrics_dict['serp_position'] == 5
                    assert metrics_dict['serp_competitors_count'] == 3
                    assert 'rich_snippets' in metrics_dict['serp_features']
                    assert len(metrics_dict['serp_top_competitors']) == 3

                    # Verify description includes SERP insights
                    assert 'python tutorial' in diagnosis.description
                    assert '#5' in diagnosis.description
                    assert 'realpython.com' in diagnosis.description

    def test_competitor_insight_created(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test competitor insights are created from CSE data"""
        risk = Mock()
        risk.id = "risk-2"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    diagnosis = detector._diagnose_risk(risk)

                    # Verify competitor data in diagnosis
                    assert diagnosis is not None
                    metrics_dict = diagnosis.metrics.dict()

                    # Check top competitors
                    competitors = metrics_dict['serp_top_competitors']
                    assert len(competitors) == 3
                    assert competitors[0]['domain'] == 'realpython.com'
                    assert competitors[0]['position'] == 1
                    assert competitors[0]['has_rich_snippet'] is True

                    # Verify description mentions competitors
                    assert 'realpython.com' in diagnosis.description
                    assert 'tutorialspoint.com' in diagnosis.description
                    assert 'w3schools.com' in diagnosis.description

    def test_serp_feature_insight_created(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test SERP feature insights are created"""
        risk = Mock()
        risk.id = "risk-3"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    diagnosis = detector._diagnose_risk(risk)

                    # Verify SERP features in diagnosis
                    assert diagnosis is not None
                    metrics_dict = diagnosis.metrics.dict()

                    # Check SERP features
                    features = metrics_dict['serp_features']
                    assert 'rich_snippets' in features
                    assert 'thumbnails' in features
                    assert 'breadcrumbs' in features

                    # Verify description mentions SERP features
                    assert 'SERP features detected' in diagnosis.description
                    assert 'rich_snippets' in diagnosis.description

    def test_rich_snippet_competitor_detection(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test detection of competitors with rich snippets"""
        risk = Mock()
        risk.id = "risk-4"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    diagnosis = detector._diagnose_risk(risk)

                    # Verify rich snippet detection
                    assert diagnosis is not None

                    # Check that description mentions rich snippets
                    # 2 of top 3 competitors have rich snippets
                    assert '2 of top 3 competitors have rich snippets' in diagnosis.description

    def test_domain_not_found_in_serp(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test diagnosis when domain is not found in SERP"""
        # Modify mock to return None for target_position
        mock_cse_analyzer.analyze_serp.return_value['target_position'] = None

        risk = Mock()
        risk.id = "risk-5"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    diagnosis = detector._diagnose_risk(risk)

                    # Verify diagnosis mentions domain not found
                    assert diagnosis is not None
                    assert 'not found in top' in diagnosis.description

    def test_no_top_query_skips_cse(
        self, mock_repository, mock_config, mock_db_connection, mock_cse_analyzer
    ):
        """Test that CSE is skipped when no top query is available"""
        # Modify mock to return None for top_query
        cursor = mock_db_connection.return_value.cursor.return_value
        row_data = cursor.fetchone.return_value.copy()
        row_data['top_query'] = None
        cursor.fetchone.return_value = row_data

        risk = Mock()
        risk.id = "risk-6"  # String ID for pydantic validation
        risk.property = 'sc-domain:example.com'
        risk.entity_id = '/blog/tutorial'
        risk.category = InsightCategory.RISK
        risk.severity = InsightSeverity.HIGH

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            with patch('insights_core.detectors.diagnosis.EVENT_CORRELATION_AVAILABLE', False):
                with patch('insights_core.detectors.diagnosis.CAUSAL_ANALYZER_AVAILABLE', False):
                    detector = DiagnosisDetector(
                        mock_repository, mock_config,
                        use_correlation=False,
                        use_causal_analysis=False,
                        use_cse=True
                    )
                    detector._cse_analyzer = mock_cse_analyzer

                    diagnosis = detector._diagnose_risk(risk)

                    # Verify CSE was not called
                    mock_cse_analyzer.analyze_serp.assert_not_called()

                    # Diagnosis should still be created
                    assert diagnosis is not None
                    assert diagnosis.category == InsightCategory.DIAGNOSIS


class TestCseIntegrationEdgeCases:
    """Test edge cases in CSE integration"""

    @pytest.fixture
    def mock_repository(self):
        """Mock InsightRepository"""
        repo = Mock()
        repo.create = Mock(return_value=Mock(id=1))
        repo.update = Mock()
        return repo

    @pytest.fixture
    def mock_config(self):
        """Mock InsightsConfig"""
        config = Mock()
        config.warehouse_dsn = "postgresql://test:test@localhost/test"
        return config

    def test_empty_competitors_list(self, mock_repository, mock_config):
        """Test handling of empty competitors list"""
        mock_cse = Mock()
        mock_cse.get_quota_status = Mock(return_value={'remaining': 90})
        mock_cse.analyze_serp = Mock(return_value={
            'query': 'test',
            'target_domain': 'example.com',
            'target_position': 1,
            'competitors': [],
            'serp_features': [],
            'total_results': 1,
            'analyzed_at': datetime.utcnow().isoformat()
        })

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse

            result = detector._get_serp_context('sc-domain:example.com', 'test')

            # Should handle empty competitors gracefully
            assert result is not None
            assert result['competitors'] == []

    def test_missing_optional_fields(self, mock_repository, mock_config):
        """Test handling of missing optional fields in SERP response"""
        mock_cse = Mock()
        mock_cse.get_quota_status = Mock(return_value={'remaining': 90})
        mock_cse.analyze_serp = Mock(return_value={
            'query': 'test',
            'target_domain': 'example.com',
            # Missing optional fields
        })

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse

            result = detector._get_serp_context('sc-domain:example.com', 'test')

            # Should handle missing fields gracefully
            assert result is not None
            assert result.get('target_position') is None
            assert result.get('competitors', []) == []

    def test_cse_timeout_handling(self, mock_repository, mock_config):
        """Test handling of CSE timeout errors"""
        mock_cse = Mock()
        mock_cse.get_quota_status = Mock(return_value={'remaining': 90})
        mock_cse.analyze_serp = Mock(side_effect=TimeoutError("Request timeout"))

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse

            result = detector._get_serp_context('sc-domain:example.com', 'test')

            # Should return None on timeout
            assert result is None

    def test_multiple_serp_features(self, mock_repository, mock_config):
        """Test handling of multiple SERP features"""
        mock_cse = Mock()
        mock_cse.get_quota_status = Mock(return_value={'remaining': 90})
        mock_cse.analyze_serp = Mock(return_value={
            'query': 'test',
            'target_domain': 'example.com',
            'target_position': 1,
            'competitors': [],
            'serp_features': [
                'rich_snippets',
                'thumbnails',
                'breadcrumbs',
                'ratings',
                'sitelinks'
            ],
            'total_results': 10,
            'analyzed_at': datetime.utcnow().isoformat()
        })

        with patch('insights_core.detectors.diagnosis.CSE_ANALYZER_AVAILABLE', True):
            detector = DiagnosisDetector(mock_repository, mock_config, use_cse=True)
            detector._cse_analyzer = mock_cse

            result = detector._get_serp_context('sc-domain:example.com', 'test')

            # Should handle multiple features
            assert result is not None
            assert len(result['serp_features']) == 5
            assert 'rich_snippets' in result['serp_features']
            assert 'sitelinks' in result['serp_features']
