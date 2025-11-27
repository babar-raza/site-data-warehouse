"""
Content Analyzer - AI-Powered Content Quality Assessment
========================================================
Uses Ollama (local LLM) for intelligent content analysis:
- Content quality scoring
- Topic extraction
- Readability analysis
- SEO optimization suggestions
- Sentiment analysis

All processing is local (no external API calls)
"""
import hashlib
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

import asyncpg
import httpx
from bs4 import BeautifulSoup
from readability import Document
from textstat import flesch_reading_ease, flesch_kincaid_grade

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    """
    Analyzes content quality using Ollama and NLP libraries
    """

    def __init__(
        self,
        db_dsn: str = None,
        ollama_url: str = None,
        model: str = 'llama3.1:8b'
    ):
        """
        Initialize content analyzer

        Args:
            db_dsn: Database connection string
            ollama_url: Ollama API URL
            model: LLM model to use
        """
        self.db_dsn = db_dsn or os.getenv('WAREHOUSE_DSN')
        self.ollama_url = ollama_url or os.getenv('OLLAMA_URL', 'http://localhost:11434')
        self.model = model
        self._pool: Optional[asyncpg.Pool] = None

        logger.info(f"ContentAnalyzer initialized with model: {model}")

    async def get_pool(self) -> asyncpg.Pool:
        """Get or create database connection pool"""
        if not self._pool:
            self._pool = await asyncpg.create_pool(self.db_dsn, min_size=2, max_size=10)
        return self._pool

    async def close(self):
        """Close database connections"""
        if self._pool:
            await self._pool.close()

    def extract_text(self, html: str) -> Dict:
        """
        Extract clean text and metadata from HTML

        Args:
            html: Raw HTML content

        Returns:
            Dict with text, title, meta, structure
        """
        try:
            soup = BeautifulSoup(html, 'lxml')

            # Use readability to extract main content
            doc = Document(html)
            clean_html = doc.summary()
            clean_soup = BeautifulSoup(clean_html, 'lxml')

            # Extract text
            text = clean_soup.get_text(separator=' ', strip=True)

            # Extract metadata
            title = doc.title()
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            meta_description = meta_desc['content'] if meta_desc and 'content' in meta_desc.attrs else ''

            # Extract headings
            h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all('h1')]
            h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all('h2')]
            h3_tags = [h3.get_text(strip=True) for h3 in soup.find_all('h3')]

            # Count elements
            images = len(soup.find_all('img'))
            links = len(soup.find_all('a'))
            internal_links = len([a for a in soup.find_all('a', href=True) if not a['href'].startswith('http')])
            external_links = links - internal_links

            # Text metrics
            words = text.split()
            word_count = len(words)
            char_count = len(text)
            sentences = text.split('.')
            sentence_count = len([s for s in sentences if s.strip()])
            paragraphs = [p.get_text(strip=True) for p in soup.find_all('p')]
            paragraph_count = len([p for p in paragraphs if p])

            return {
                'text': text,
                'title': title,
                'meta_description': meta_description,
                'h1_tags': h1_tags,
                'h2_tags': h2_tags,
                'h3_tags': h3_tags,
                'word_count': word_count,
                'character_count': char_count,
                'sentence_count': sentence_count,
                'paragraph_count': paragraph_count,
                'image_count': images,
                'link_count': links,
                'internal_link_count': internal_links,
                'external_link_count': external_links
            }

        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            return {'text': '', 'error': str(e)}

    def calculate_readability(self, text: str) -> Dict:
        """
        Calculate readability scores

        Args:
            text: Plain text content

        Returns:
            Dict with readability metrics
        """
        try:
            if not text or len(text.strip()) < 100:
                return {'flesch_reading_ease': 0, 'flesch_kincaid_grade': 0}

            return {
                'flesch_reading_ease': round(flesch_reading_ease(text), 2),
                'flesch_kincaid_grade': round(flesch_kincaid_grade(text), 2)
            }

        except Exception as e:
            logger.error(f"Error calculating readability: {e}")
            return {'flesch_reading_ease': 0, 'flesch_kincaid_grade': 0}

    async def analyze_with_ollama(self, text: str, prompt_type: str = 'quality') -> Dict:
        """
        Analyze content using Ollama LLM

        Args:
            text: Content to analyze
            prompt_type: Type of analysis (quality, topics, suggestions)

        Returns:
            Analysis results
        """
        try:
            # Limit input size
            text_sample = text[:3000] if len(text) > 3000 else text

            prompts = {
                'quality': f"""Analyze this content and provide:
1. Overall quality score (0-100)
2. Key topics covered (comma-separated)
3. Target audience
4. Sentiment (positive/neutral/negative)

Content: {text_sample}

Respond in JSON format with keys: quality_score, topics, audience, sentiment""",

                'suggestions': f"""Analyze this content and provide improvement suggestions:

Content: {text_sample}

List 3-5 specific, actionable improvements. Be concise.""",

                'summary': f"""Provide a one-paragraph summary of this content:

Content: {text_sample}"""
            }

            prompt = prompts.get(prompt_type, prompts['quality'])

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "stream": False
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    return {'response': result.get('response', ''), 'success': True}
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    return {'response': '', 'success': False, 'error': response.status_code}

        except Exception as e:
            logger.error(f"Error analyzing with Ollama: {e}")
            return {'response': '', 'success': False, 'error': str(e)}

    def parse_llm_quality_response(self, response: str) -> Dict:
        """
        Parse LLM response for quality analysis

        Args:
            response: Raw LLM response

        Returns:
            Parsed quality metrics
        """
        try:
            import json
            import re

            # Try to extract JSON
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    'quality_score': float(data.get('quality_score', 50)),
                    'topics': data.get('topics', '').split(',') if isinstance(data.get('topics'), str) else data.get('topics', []),
                    'audience': data.get('audience', 'general'),
                    'sentiment': data.get('sentiment', 'neutral')
                }

            # Fallback: parse text manually
            quality_match = re.search(r'quality[_\s]score[:\s]*(\d+)', response, re.IGNORECASE)
            quality_score = int(quality_match.group(1)) if quality_match else 50

            return {
                'quality_score': quality_score,
                'topics': [],
                'audience': 'general',
                'sentiment': 'neutral'
            }

        except Exception as e:
            logger.error(f"Error parsing LLM response: {e}")
            return {
                'quality_score': 50,
                'topics': [],
                'audience': 'general',
                'sentiment': 'neutral'
            }

    async def analyze(
        self,
        property: str,
        page_path: str,
        html_content: str
    ) -> Dict:
        """
        Complete content analysis pipeline

        Args:
            property: Property URL
            page_path: Page path
            html_content: Raw HTML

        Returns:
            Complete analysis results
        """
        try:
            logger.info(f"Analyzing content for {property}{page_path}")

            # Extract text and metadata
            extracted = self.extract_text(html_content)

            if 'error' in extracted:
                return {'error': extracted['error']}

            text = extracted['text']

            # Calculate readability
            readability = self.calculate_readability(text)

            # Analyze with Ollama (quality)
            quality_analysis = await self.analyze_with_ollama(text, 'quality')
            quality_metrics = self.parse_llm_quality_response(quality_analysis.get('response', ''))

            # Get improvement suggestions
            suggestions_analysis = await self.analyze_with_ollama(text, 'suggestions')
            suggestions_text = suggestions_analysis.get('response', '')

            # Parse suggestions into list
            suggestions = [s.strip() for s in suggestions_text.split('\n') if s.strip() and len(s.strip()) > 10][:5]

            # Calculate overall score (weighted)
            readability_score = min(readability['flesch_reading_ease'], 100)
            llm_score = quality_metrics['quality_score']

            # Weight: 40% LLM, 30% readability, 30% structure
            structure_score = min((extracted['word_count'] / 10), 100)  # 1000 words = 100 points
            overall_score = (0.4 * llm_score + 0.3 * readability_score + 0.3 * structure_score)

            # Store in database
            pool = await self.get_pool()

            async with pool.acquire() as conn:
                # First ensure we have a snapshot
                snapshot_id = await conn.fetchval("""
                    INSERT INTO content.page_snapshots (
                        property,
                        page_path,
                        url,
                        html_content,
                        text_content,
                        title,
                        meta_description,
                        h1_tags,
                        h2_tags,
                        h3_tags,
                        word_count,
                        character_count,
                        paragraph_count,
                        sentence_count,
                        image_count,
                        link_count,
                        internal_link_count,
                        external_link_count,
                        flesch_reading_ease,
                        flesch_kincaid_grade,
                        content_hash,
                        snapshot_date
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21, $22)
                    ON CONFLICT (property, page_path, snapshot_date)
                    DO UPDATE SET
                        text_content = EXCLUDED.text_content,
                        word_count = EXCLUDED.word_count,
                        flesch_reading_ease = EXCLUDED.flesch_reading_ease
                    RETURNING snapshot_id
                """,
                    property, page_path, f"{property}{page_path}",
                    html_content, text,
                    extracted['title'], extracted['meta_description'],
                    extracted['h1_tags'], extracted['h2_tags'], extracted['h3_tags'],
                    extracted['word_count'], extracted['character_count'],
                    extracted['paragraph_count'], extracted['sentence_count'],
                    extracted['image_count'], extracted['link_count'],
                    extracted['internal_link_count'], extracted['external_link_count'],
                    readability['flesch_reading_ease'], readability['flesch_kincaid_grade'],
                    hashlib.sha256(text.encode()).hexdigest(),
                    datetime.utcnow().date()
                )

                # Store quality scores
                await conn.execute("""
                    INSERT INTO content.quality_scores (
                        property,
                        page_path,
                        snapshot_id,
                        overall_score,
                        readability_score,
                        relevance_score,
                        depth_score,
                        optimization_score,
                        content_summary,
                        key_topics,
                        sentiment,
                        target_audience,
                        improvement_suggestions,
                        analyzed_by,
                        model_version,
                        confidence
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                """,
                    property, page_path, snapshot_id,
                    round(overall_score, 2),
                    round(readability_score, 2),
                    round(llm_score, 2),
                    round(structure_score, 2),
                    round(llm_score * 0.9, 2),  # optimization score
                    quality_analysis.get('response', '')[:500],  # summary
                    quality_metrics['topics'],
                    quality_metrics['sentiment'],
                    quality_metrics['audience'],
                    suggestions,
                    'ollama',
                    self.model,
                    0.8  # confidence
                )

            logger.info(f"Analysis complete: {property}{page_path} scored {overall_score:.1f}")

            return {
                'property': property,
                'page_path': page_path,
                'overall_score': round(overall_score, 2),
                'readability': readability,
                'quality_metrics': quality_metrics,
                'suggestions': suggestions,
                'extracted': extracted,
                'snapshot_id': snapshot_id,
                'success': True
            }

        except Exception as e:
            logger.error(f"Error in content analysis: {e}")
            return {'error': str(e), 'success': False}

    def analyze_sync(self, property: str, page_path: str, html_content: str) -> Dict:
        """Sync wrapper for Celery"""
        import asyncio
        return asyncio.run(self.analyze(property, page_path, html_content))
