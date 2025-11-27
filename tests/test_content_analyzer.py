"""
Tests for Content Analyzer
"""
import pytest
from insights_core.content_analyzer import ContentAnalyzer


class TestContentAnalyzer:
    """Test content analysis functionality"""

    def test_initialization(self):
        """Test content analyzer initialization"""
        analyzer = ContentAnalyzer(model='llama3.1:8b')
        assert analyzer.model == 'llama3.1:8b'
        assert analyzer.ollama_url is not None

    def test_extract_text_basic(self):
        """Test basic text extraction"""
        analyzer = ContentAnalyzer()

        html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="Test description">
            </head>
            <body>
                <h1>Main Heading</h1>
                <h2>Subheading</h2>
                <p>This is a test paragraph.</p>
                <p>Another paragraph here.</p>
                <a href="/internal">Internal link</a>
                <a href="https://external.com">External link</a>
                <img src="image.jpg">
            </body>
        </html>
        """

        extracted = analyzer.extract_text(html)

        assert 'text' in extracted
        assert 'title' in extracted
        assert 'meta_description' in extracted
        assert extracted['title'] == 'Test Page'
        assert extracted['meta_description'] == 'Test description'
        assert len(extracted['h1_tags']) == 1
        assert len(extracted['h2_tags']) == 1
        assert extracted['image_count'] == 1
        assert extracted['link_count'] == 2
        assert extracted['word_count'] > 0

    def test_extract_text_empty(self):
        """Test extraction with empty HTML"""
        analyzer = ContentAnalyzer()
        html = "<html></html>"

        extracted = analyzer.extract_text(html)

        assert 'text' in extracted
        assert extracted['text'] == '' or extracted['word_count'] == 0

    def test_calculate_readability(self):
        """Test readability calculation"""
        analyzer = ContentAnalyzer()

        text = """
        This is a simple test text. It has short sentences.
        The readability should be high. Easy to understand content.
        Testing Flesch Reading Ease and Flesch-Kincaid Grade scores.
        """

        readability = analyzer.calculate_readability(text)

        assert 'flesch_reading_ease' in readability
        assert 'flesch_kincaid_grade' in readability
        assert 0 <= readability['flesch_reading_ease'] <= 100
        assert readability['flesch_kincaid_grade'] >= 0

    def test_calculate_readability_short_text(self):
        """Test readability with too-short text"""
        analyzer = ContentAnalyzer()
        short_text = "Too short"

        readability = analyzer.calculate_readability(short_text)

        assert readability['flesch_reading_ease'] == 0
        assert readability['flesch_kincaid_grade'] == 0

    def test_parse_llm_quality_response(self):
        """Test parsing LLM quality response"""
        analyzer = ContentAnalyzer()

        # Test with valid JSON response
        json_response = '''
        {
            "quality_score": 85,
            "topics": "SEO, Content Marketing, Analytics",
            "audience": "marketers",
            "sentiment": "positive"
        }
        '''

        parsed = analyzer.parse_llm_quality_response(json_response)

        assert parsed['quality_score'] == 85
        assert isinstance(parsed['topics'], list)
        assert parsed['audience'] == 'marketers'
        assert parsed['sentiment'] == 'positive'

    def test_parse_llm_quality_response_text(self):
        """Test parsing text-based LLM response"""
        analyzer = ContentAnalyzer()

        # Test with text response
        text_response = "The quality score for this content is 75 out of 100."

        parsed = analyzer.parse_llm_quality_response(text_response)

        assert parsed['quality_score'] == 75
        assert isinstance(parsed['topics'], list)

    @pytest.mark.asyncio
    async def test_analyze_with_ollama_mock(self, mocker):
        """Test Ollama analysis (mocked)"""
        analyzer = ContentAnalyzer()

        # Mock httpx client
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '{"quality_score": 80, "topics": "tech", "audience": "developers", "sentiment": "neutral"}'
        }

        mock_client = mocker.Mock()
        mock_client.post = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        result = await analyzer.analyze_with_ollama("Test content", "quality")

        assert result['success']
        assert 'response' in result

    @pytest.mark.asyncio
    async def test_analyze_complete_mock(self, mocker):
        """Test complete analysis pipeline (mocked)"""
        analyzer = ContentAnalyzer()

        # Mock database
        mock_pool = mocker.AsyncMock()
        mock_conn = mocker.AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        mock_conn.fetchval.return_value = 'mock-snapshot-id'

        analyzer._pool = mock_pool

        # Mock Ollama
        mock_response = mocker.Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'response': '{"quality_score": 85, "topics": ["SEO"], "audience": "marketers", "sentiment": "positive"}'
        }

        mock_client = mocker.Mock()
        mock_client.post = mocker.AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = mocker.AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = mocker.AsyncMock(return_value=None)

        mocker.patch('httpx.AsyncClient', return_value=mock_client)

        html = "<html><head><title>Test</title></head><body><p>Content for testing.</p></body></html>"

        result = await analyzer.analyze(
            property="https://example.com",
            page_path="/test/",
            html_content=html
        )

        assert result['success']
        assert 'overall_score' in result
        assert result['overall_score'] > 0


class TestContentQualityMetrics:
    """Test content quality assessment"""

    def test_structure_scoring(self):
        """Test that structure affects score"""
        analyzer = ContentAnalyzer()

        # Short content
        short_html = "<html><body><p>Short content.</p></body></html>"
        short_extracted = analyzer.extract_text(short_html)

        # Long content
        long_content = " ".join(["This is a sentence."] * 200)
        long_html = f"<html><body><p>{long_content}</p></body></html>"
        long_extracted = analyzer.extract_text(long_html)

        assert long_extracted['word_count'] > short_extracted['word_count']

    def test_heading_extraction(self):
        """Test heading structure extraction"""
        analyzer = ContentAnalyzer()

        html = """
        <html><body>
            <h1>Main Heading 1</h1>
            <h1>Main Heading 2</h1>
            <h2>Sub 1</h2>
            <h2>Sub 2</h2>
            <h2>Sub 3</h2>
            <h3>Detail 1</h3>
        </body></html>
        """

        extracted = analyzer.extract_text(html)

        assert len(extracted['h1_tags']) == 2
        assert len(extracted['h2_tags']) == 3
        assert len(extracted['h3_tags']) == 1
        assert 'Main Heading 1' in extracted['h1_tags']
