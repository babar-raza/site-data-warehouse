"""
Hugo Content Writer Service
===========================
Executes content optimization actions by modifying Hugo markdown files directly.

Features:
- Reads .md files with YAML/TOML frontmatter
- Generates optimizations via Ollama LLM
- Writes changes back to filesystem
- Updates action status to 'completed'
- Updates insight status to 'actioned'
- Logs all changes for audit trail

Usage:
    from services.hugo_content_writer import HugoContentWriter
    from config.hugo_config import HugoConfig

    config = HugoConfig.from_env()
    writer = HugoContentWriter(config=config, db_connection=conn)
    result = writer.execute_action(action_id)
"""
import hashlib
import logging
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import frontmatter
import httpx
import psycopg2
import psycopg2.extras
from pydantic import ValidationError

from config.hugo_config import HugoConfig
from insights_core.prompts import get_prompt
from insights_core.prompts.schemas import (
    TitleOptimizationResponse,
    MetaDescriptionResponse,
    ContentExpansionResponse,
    ReadabilityResponse,
    KeywordOptimizationResponse,
    IntentDifferentiationResponse,
)

logger = logging.getLogger(__name__)

# Feature flag for structured prompts (set to false to use legacy free-form parsing)
USE_STRUCTURED_PROMPTS = os.environ.get("USE_STRUCTURED_PROMPTS", "true").lower() == "true"


class HugoContentWriter:
    """
    Executes content optimization actions by modifying Hugo markdown files.

    Reads action details from database, resolves the target file path,
    applies AI-generated optimizations, and updates status on completion.
    """

    def __init__(
        self,
        config: HugoConfig,
        db_connection,
        ollama_base_url: str = "http://localhost:11434",
        ollama_model: str = "llama3.1",
        use_structured_client: bool = True
    ):
        """
        Initialize HugoContentWriter.

        Args:
            config: HugoConfig instance with content path settings
            db_connection: Database connection (psycopg2)
            ollama_base_url: Ollama API base URL
            ollama_model: Model name to use for generation
            use_structured_client: Use Instructor client for structured outputs
        """
        self.config = config
        self.db = db_connection
        self.ollama_base_url = ollama_base_url
        self.ollama_model = ollama_model
        self.use_structured_client = use_structured_client and USE_STRUCTURED_PROMPTS

        # Initialize structured client if enabled
        self._llm_client = None
        if self.use_structured_client:
            try:
                from insights_core.prompts.client import ContentOptimizationClient
                self._llm_client = ContentOptimizationClient(
                    provider="ollama",
                    base_url=ollama_base_url,
                    model=ollama_model,
                    max_retries=2,
                    enable_cache=True
                )
                logger.info("Structured LLM client initialized")
            except ImportError as e:
                logger.warning(f"Could not initialize structured client: {e}")
                self.use_structured_client = False

        logger.info(f"HugoContentWriter initialized")
        logger.info(f"  Content path: {config.content_path}")
        logger.info(f"  Ollama model: {ollama_model}")
        logger.info(f"  Structured prompts: {self.use_structured_client}")

    def execute_action(self, action_id: str) -> Dict[str, Any]:
        """
        Execute a content optimization action.

        Args:
            action_id: UUID of the action to execute

        Returns:
            Dict with execution result:
            {
                "success": bool,
                "action_id": str,
                "file_path": str (if applicable),
                "changes_made": list,
                "error": str (if failed)
            }
        """
        result: Dict[str, Any] = {
            "success": False,
            "action_id": action_id,
            "started_at": datetime.utcnow().isoformat()
        }

        try:
            # 1. Fetch action details
            action = self._get_action(action_id)
            if not action:
                result["error"] = f"Action {action_id} not found"
                logger.error(result["error"])
                return result

            logger.info(f"Executing action: {action.get('title', action_id)}")
            logger.info(f"  Type: {action.get('action_type')}")
            logger.info(f"  Property: {action.get('property')}")

            # 2. Mark action as in_progress
            self._update_action_status(action_id, "in_progress")

            # 3. Resolve file path
            file_path = self._resolve_file_path(action)
            if not file_path:
                result["error"] = "Could not resolve file path from action metadata"
                logger.error(result["error"])
                self._update_action_status(action_id, "pending")  # Revert
                return result

            result["file_path"] = file_path

            if not os.path.exists(file_path):
                result["error"] = f"File not found: {file_path}"
                logger.error(result["error"])
                self._update_action_status(action_id, "pending")  # Revert
                return result

            # 4. Read current content
            try:
                post = frontmatter.load(file_path)
            except Exception as e:
                result["error"] = f"Failed to parse markdown file: {e}"
                logger.error(result["error"])
                self._update_action_status(action_id, "pending")
                return result

            original_content = post.content
            original_metadata = dict(post.metadata)

            # 5. Apply optimizations based on action type
            optimization_result = self._apply_optimizations(
                action=action,
                metadata=post.metadata,
                content=post.content
            )

            result["changes_made"] = optimization_result["changes"]

            if optimization_result["modified"]:
                # 6. Write back to file
                post.metadata = optimization_result["metadata"]
                post.content = optimization_result["content"]

                # Preserve line endings (CRLF on Windows)
                with open(file_path, 'w', encoding='utf-8', newline='') as f:
                    f.write(frontmatter.dumps(post))

                logger.info(f"File updated: {file_path}")
                for change in optimization_result["changes"]:
                    logger.info(f"  - {change}")

                # 7. Log change to hugo_changes table
                self._log_change(
                    action=action,
                    file_path=file_path,
                    original_metadata=original_metadata,
                    new_metadata=optimization_result["metadata"],
                    original_content=original_content,
                    new_content=optimization_result["content"],
                    changes=optimization_result["changes"]
                )
            else:
                logger.info("No changes made (content already optimal or LLM returned same)")

            # 8. Update statuses
            outcome = {
                "changes_made": optimization_result["changes"],
                "file_path": file_path,
                "completed_at": datetime.utcnow().isoformat(),
                "modified": optimization_result["modified"]
            }
            self._update_action_status(action_id, "completed", outcome=outcome)

            # Update linked insight status to 'actioned'
            if action.get("insight_id"):
                self._update_insight_status(action["insight_id"], "actioned")

            result["success"] = True
            result["completed_at"] = datetime.utcnow().isoformat()
            logger.info(f"Action {action_id} completed successfully")

        except Exception as e:
            logger.exception(f"Failed to execute action {action_id}")
            result["error"] = str(e)
            # Revert status on failure
            try:
                self._update_action_status(action_id, "pending")
            except Exception:
                pass  # Don't mask original error

        return result

    def _get_action(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Fetch action from database."""
        try:
            with self.db.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("""
                    SELECT
                        id, insight_id, property, action_type, title,
                        description, instructions, priority, effort,
                        estimated_impact, status, metadata, entity_id
                    FROM gsc.actions
                    WHERE id = %s
                """, (action_id,))
                row = cur.fetchone()

                if row:
                    return dict(row)
        except Exception as e:
            logger.error(f"Failed to fetch action {action_id}: {e}")
        return None

    def _resolve_file_path(self, action: Dict[str, Any]) -> Optional[str]:
        """
        Resolve the filesystem path for the action's target page.

        Extracts subdomain from property URL and page_path from metadata.
        """
        metadata = action.get("metadata") or {}

        # Extract subdomain from property URL
        property_url = action.get("property", "")
        subdomain = self.config.extract_subdomain(property_url)

        if not subdomain:
            logger.warning(f"Could not extract subdomain from: {property_url}")
            return None

        # Get page path from action metadata or entity_id
        page_path = metadata.get("page_path") or action.get("entity_id", "")

        if not page_path:
            logger.warning("No page_path in action metadata or entity_id")
            return None

        # Get locale if specified
        locale = metadata.get("locale", self.config.default_locale)

        return self.config.get_content_file_path(subdomain, page_path, locale)

    def _apply_optimizations(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Dict[str, Any]:
        """
        Apply optimizations based on action type.

        Routes to specific optimization methods based on action_type
        and template_name in metadata.

        Returns:
            {
                "modified": bool,
                "metadata": dict,
                "content": str,
                "changes": list
            }
        """
        action_type = action.get("action_type", "")
        action_metadata = action.get("metadata") or {}
        template_name = action_metadata.get("template_name", "")

        logger.debug(f"Applying optimizations: type={action_type}, template={template_name}")

        changes: List[str] = []
        modified = False
        new_metadata = dict(metadata)
        new_content = content

        # Route to specific optimizer
        if action_type == "content_update":
            if "title" in template_name.lower() or "seo_title" in template_name.lower():
                new_metadata, changes, modified = self._optimize_title(
                    action, new_metadata, new_content
                )
            elif "meta_description" in template_name.lower():
                new_metadata, changes, modified = self._optimize_meta_description(
                    action, new_metadata, new_content
                )
            elif "content_expansion" in template_name.lower() or "thin_content" in template_name.lower():
                new_content, changes, modified = self._expand_content(
                    action, new_metadata, new_content
                )
            elif "keyword" in template_name.lower():
                new_content, changes, modified = self._optimize_keywords(
                    action, new_metadata, new_content
                )
            elif "readability" in template_name.lower():
                new_content, changes, modified = self._improve_readability(
                    action, new_metadata, new_content
                )
            else:
                logger.warning(f"Unknown template_name for content_update: {template_name}")

        elif action_type == "content_restructure":
            if "cannibalization" in template_name.lower():
                new_content, changes, modified = self._fix_cannibalization(
                    action, new_metadata, new_content
                )
            else:
                logger.warning(f"Unknown template_name for content_restructure: {template_name}")

        else:
            logger.warning(f"Unknown action_type: {action_type}")

        return {
            "modified": modified,
            "metadata": new_metadata,
            "content": new_content,
            "changes": changes
        }

    def _optimize_title(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[Dict[str, Any], List[str], bool]:
        """Generate optimized title using LLM."""
        current_title = metadata.get("title", "")
        action_metadata = action.get("metadata") or {}

        prompt = get_prompt(
            "title_optimization",
            current_title=current_title,
            topic=action.get("description", ""),
            keywords=action_metadata.get("keywords", []),
            ctr=action_metadata.get("ctr", 0),
            position=action_metadata.get("position", 0)
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=TitleOptimizationResponse,
                    operation_type="title_optimization"
                )
                new_title = response.optimized_title
                changes = [f"Title: '{current_title}' -> '{new_title}'"]
                if response.changes_made:
                    changes.extend(response.changes_made)

                if new_title and new_title != current_title:
                    metadata["title"] = new_title
                    return metadata, changes, True

                return metadata, [], False

            except ValidationError as e:
                logger.warning(f"Title validation failed, falling back to legacy: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed, falling back to legacy: {e}")

        # Legacy fallback: free-form text parsing
        raw_response = self._call_ollama(prompt).strip()
        new_title = raw_response.strip('"\'')

        if new_title and new_title != current_title and len(new_title) <= 70:
            metadata["title"] = new_title
            return metadata, [f"Title: '{current_title}' -> '{new_title}'"], True

        return metadata, [], False

    def _optimize_meta_description(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[Dict[str, Any], List[str], bool]:
        """Generate or optimize meta description using LLM."""
        current_desc = metadata.get("description", "")
        action_metadata = action.get("metadata") or {}

        # Get first 500 chars of content for context
        content_preview = content[:500] if content else ""

        prompt = get_prompt(
            "meta_description",
            title=metadata.get("title", ""),
            content_preview=content_preview,
            keywords=action_metadata.get("keywords", [])
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=MetaDescriptionResponse,
                    operation_type="meta_description"
                )
                new_desc = response.description

                if new_desc and new_desc != current_desc:
                    metadata["description"] = new_desc
                    old_preview = f"'{current_desc[:50]}...'" if current_desc else "None"
                    changes = [f"Description: {old_preview} -> '{new_desc[:50]}...'"]
                    if response.includes_cta:
                        changes.append("Added call-to-action")
                    return metadata, changes, True

                return metadata, [], False

            except ValidationError as e:
                logger.warning(f"Meta description validation failed: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed: {e}")

        # Legacy fallback
        new_desc = self._call_ollama(prompt).strip().strip('"\'')

        if new_desc and new_desc != current_desc and 100 <= len(new_desc) <= 180:
            metadata["description"] = new_desc
            old_preview = f"'{current_desc[:50]}...'" if current_desc else "None"
            return metadata, [f"Description: {old_preview} -> '{new_desc[:50]}...'"], True

        return metadata, [], False

    def _expand_content(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[str, List[str], bool]:
        """Expand thin content using LLM."""
        word_count = len(content.split())
        action_metadata = action.get("metadata") or {}

        # Don't expand if already adequate
        if word_count >= 500:
            return content, ["Content already adequate length"], False

        target_words = action_metadata.get("target_words", 300)
        competitor_avg = action_metadata.get("competitor_avg", 1000)

        prompt = get_prompt(
            "content_expansion",
            title=metadata.get("title", ""),
            content=content,
            word_count=word_count,
            keywords=action_metadata.get("keywords", []),
            competitor_avg=competitor_avg,
            target_words=target_words
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=ContentExpansionResponse,
                    operation_type="content_expansion"
                )
                expanded = response.expanded_content
                new_word_count = len(expanded.split())

                if expanded and new_word_count > word_count + 50:
                    changes = [f"Content expanded: {word_count} -> {new_word_count} words"]
                    if response.sections_added:
                        changes.append(f"Sections added: {', '.join(response.sections_added)}")
                    return expanded, changes, True

                return content, [], False

            except ValidationError as e:
                logger.warning(f"Content expansion validation failed: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed: {e}")

        # Legacy fallback
        expanded = self._call_ollama(prompt)
        new_word_count = len(expanded.split())
        if expanded and new_word_count > word_count + 100:
            return expanded, [f"Content expanded: {word_count} -> {new_word_count} words"], True

        return content, [], False

    def _optimize_keywords(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[str, List[str], bool]:
        """Optimize content for target keywords."""
        action_metadata = action.get("metadata") or {}
        keywords = action_metadata.get("keywords", [])

        if not keywords:
            return content, [], False

        density = action_metadata.get("keyword_density", 0)

        prompt = get_prompt(
            "keyword_optimization",
            keywords=keywords,
            density=density,
            content=content[:3000]  # Limit for context window
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=KeywordOptimizationResponse,
                    operation_type="keyword_optimization"
                )
                optimized = response.optimized_content

                if optimized and optimized != content:
                    keywords_str = ", ".join(keywords[:3]) if isinstance(keywords, list) else str(keywords)
                    changes = [f"Optimized for keywords: {keywords_str}"]
                    if response.keywords_added > 0:
                        changes.append(f"Keywords added: {response.keywords_added}")
                    if response.lsi_keywords_used:
                        changes.append(f"LSI keywords: {', '.join(response.lsi_keywords_used[:3])}")
                    return optimized, changes, True

                return content, [], False

            except ValidationError as e:
                logger.warning(f"Keyword optimization validation failed: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed: {e}")

        # Legacy fallback
        optimized = self._call_ollama(prompt)
        if optimized and optimized != content:
            keywords_str = ", ".join(keywords[:3]) if isinstance(keywords, list) else str(keywords)
            return optimized, [f"Optimized for keywords: {keywords_str}"], True

        return content, [], False

    def _improve_readability(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[str, List[str], bool]:
        """Improve content readability."""
        action_metadata = action.get("metadata") or {}

        flesch_score = action_metadata.get("flesch_score", 50)
        audience = action_metadata.get("audience", "general audience")

        prompt = get_prompt(
            "readability_improvement",
            flesch_score=flesch_score,
            audience=audience,
            content=content[:3000]
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=ReadabilityResponse,
                    operation_type="readability_improvement"
                )
                improved = response.improved_content

                if improved and improved != content:
                    changes = [f"Readability improved (original Flesch: {flesch_score})"]
                    if response.estimated_flesch_improvement > 0:
                        changes.append(f"Estimated improvement: +{response.estimated_flesch_improvement} points")
                    if response.changes_summary:
                        changes.extend(response.changes_summary[:3])  # Top 3 changes
                    return improved, changes, True

                return content, [], False

            except ValidationError as e:
                logger.warning(f"Readability validation failed: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed: {e}")

        # Legacy fallback
        improved = self._call_ollama(prompt)
        if improved and improved != content:
            return improved, [f"Readability improved (original Flesch: {flesch_score})"], True

        return content, [], False

    def _fix_cannibalization(
        self,
        action: Dict[str, Any],
        metadata: Dict[str, Any],
        content: str
    ) -> Tuple[str, List[str], bool]:
        """Differentiate content to avoid cannibalization."""
        action_metadata = action.get("metadata") or {}

        competing_pages = action_metadata.get("competing_pages", [])
        target_intent = action_metadata.get("target_intent", "")
        competing_intents = action_metadata.get("competing_intents", [])

        if not target_intent:
            return content, [], False

        prompt = get_prompt(
            "intent_differentiation",
            intent=target_intent,
            content=content[:2000],
            competing_intents=competing_intents or competing_pages
        )

        # Use structured client if available
        if self.use_structured_client and self._llm_client:
            try:
                response = self._llm_client.generate(
                    prompt=prompt,
                    response_model=IntentDifferentiationResponse,
                    operation_type="intent_differentiation"
                )
                differentiated = response.differentiated_content

                if differentiated and differentiated != content:
                    changes = [f"Content differentiated for intent: {response.target_intent}"]
                    if response.removed_overlap:
                        changes.append(f"Removed overlap: {', '.join(response.removed_overlap[:3])}")
                    if response.unique_value_added:
                        changes.append(f"Added unique value: {', '.join(response.unique_value_added[:3])}")
                    return differentiated, changes, True

                return content, [], False

            except ValidationError as e:
                logger.warning(f"Intent differentiation validation failed: {e}")
            except Exception as e:
                logger.warning(f"Structured generation failed: {e}")

        # Legacy fallback
        differentiated = self._call_ollama(prompt)
        if differentiated and differentiated != content:
            return differentiated, [f"Content differentiated for intent: {target_intent}"], True

        return content, [], False

    def _call_ollama(self, prompt: str) -> str:
        """
        Call Ollama LLM and return response.

        Args:
            prompt: The prompt to send to Ollama

        Returns:
            Generated text response or empty string on failure
        """
        try:
            with httpx.Client(timeout=120.0) as client:
                response = client.post(
                    f"{self.ollama_base_url}/api/generate",
                    json={
                        "model": self.ollama_model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.7,
                            "num_predict": 2000
                        }
                    }
                )

                if response.status_code == 200:
                    data = response.json()
                    return data.get("response", "")
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    logger.error(f"Response: {response.text[:500]}")
                    return ""

        except httpx.TimeoutException:
            logger.error("Ollama request timed out")
            return ""
        except Exception as e:
            logger.error(f"Ollama call failed: {e}")
            return ""

    def _update_action_status(
        self,
        action_id: str,
        status: str,
        outcome: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update action status in database."""
        try:
            with self.db.cursor() as cur:
                if status == "in_progress":
                    cur.execute("""
                        UPDATE gsc.actions
                        SET status = %s, started_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (status, action_id))
                elif status == "completed":
                    cur.execute("""
                        UPDATE gsc.actions
                        SET status = %s, completed_at = CURRENT_TIMESTAMP,
                            updated_at = CURRENT_TIMESTAMP, outcome = %s
                        WHERE id = %s
                    """, (status, psycopg2.extras.Json(outcome), action_id))
                else:
                    cur.execute("""
                        UPDATE gsc.actions
                        SET status = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE id = %s
                    """, (status, action_id))
                self.db.commit()
                logger.debug(f"Action {action_id} status updated to: {status}")
        except Exception as e:
            logger.error(f"Failed to update action status: {e}")
            self.db.rollback()

    def _update_insight_status(self, insight_id: str, status: str) -> None:
        """Update insight status in database."""
        try:
            with self.db.cursor() as cur:
                cur.execute("""
                    UPDATE gsc.insights
                    SET status = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                """, (status, insight_id))
                self.db.commit()
                logger.debug(f"Insight {insight_id} status updated to: {status}")
        except Exception as e:
            logger.error(f"Failed to update insight status: {e}")
            self.db.rollback()

    def _log_change(
        self,
        action: Dict[str, Any],
        file_path: str,
        original_metadata: Dict[str, Any],
        new_metadata: Dict[str, Any],
        original_content: str,
        new_content: str,
        changes: List[str]
    ) -> None:
        """Log change to content.hugo_changes table for audit trail."""
        try:
            action_metadata = action.get("metadata") or {}
            page_path = action_metadata.get("page_path") or action.get("entity_id", "")

            # Calculate word count change
            original_words = len(original_content.split())
            new_words = len(new_content.split())
            word_count_change = new_words - original_words

            # Generate hashes
            original_hash = hashlib.sha256(original_content.encode()).hexdigest()[:16]
            new_hash = hashlib.sha256(new_content.encode()).hexdigest()[:16]

            with self.db.cursor() as cur:
                cur.execute("""
                    INSERT INTO content.hugo_changes (
                        property, page_path, change_type,
                        old_hash, new_hash, word_count_change,
                        metadata, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                """, (
                    action.get("property"),
                    page_path,
                    "automated_optimization",
                    original_hash,
                    new_hash,
                    word_count_change,
                    psycopg2.extras.Json({
                        "action_id": str(action.get("id")),
                        "action_type": action.get("action_type"),
                        "changes": changes,
                        "file_path": file_path,
                        "automated": True,
                        "original_title": original_metadata.get("title"),
                        "new_title": new_metadata.get("title")
                    })
                ))
                self.db.commit()
                logger.debug(f"Change logged for: {page_path}")
        except Exception as e:
            logger.error(f"Failed to log change: {e}")
            # Don't fail the whole action if logging fails
            self.db.rollback()
