"""
Prompt Templates for Structured LLM Interactions

Provides standardized prompt templates for various analytical tasks including
anomaly analysis, diagnosis, and recommendation generation. Each template
includes a JSON schema for validating LLM responses.

Example usage:
    >>> from agents.base.prompt_templates import PromptTemplates
    >>> template = PromptTemplates.get_anomaly_analysis_template()
    >>> print(template['system_prompt'][:50])
    You are an expert SEO analyst...
"""
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class PromptTemplate:
    """A structured prompt template with schema validation.

    Attributes:
        name: Template identifier
        system_prompt: System-level instructions for the LLM
        user_prompt_template: Template string for user prompt (with placeholders)
        response_schema: JSON schema for validating responses
        required_placeholders: List of required placeholders in user_prompt_template
        examples: Optional few-shot examples
    """
    name: str
    system_prompt: str
    user_prompt_template: str
    response_schema: Dict[str, Any]
    required_placeholders: List[str] = field(default_factory=list)
    examples: List[Dict[str, str]] = field(default_factory=list)

    def format_user_prompt(self, **kwargs) -> str:
        """Format the user prompt template with provided values.

        Args:
            **kwargs: Values for placeholders in the template

        Returns:
            Formatted user prompt string

        Raises:
            ValueError: If required placeholders are missing
        """
        missing = [p for p in self.required_placeholders if p not in kwargs]
        if missing:
            raise ValueError(f"Missing required placeholders: {missing}")

        try:
            return self.user_prompt_template.format(**kwargs)
        except KeyError as e:
            raise ValueError(f"Missing placeholder value: {e}")


class PromptTemplates:
    """Factory class for LLM prompt templates.

    Provides standardized prompt templates for different analysis types.
    Each template includes system prompts, user prompt templates, and
    JSON schemas for response validation.

    Example:
        >>> template = PromptTemplates.get_anomaly_analysis_template()
        >>> user_prompt = template.format_user_prompt(
        ...     metric_name="clicks",
        ...     current_value=50,
        ...     historical_average=100,
        ...     percent_change=-50.0
        ... )
        >>> print(user_prompt)
    """

    # Response schemas for validation
    ANOMALY_ANALYSIS_SCHEMA = {
        "type": "object",
        "required": ["severity", "likely_causes", "recommended_actions"],
        "properties": {
            "severity": {
                "type": "string",
                "enum": ["critical", "high", "medium", "low"],
                "description": "Severity level of the anomaly"
            },
            "likely_causes": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5,
                "description": "Ranked list of most likely causes"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in the analysis (0-1)"
            },
            "recommended_actions": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": 5,
                "description": "Prioritized list of recommended actions"
            },
            "additional_data_needed": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Additional data that would improve analysis"
            },
            "reasoning": {
                "type": "string",
                "description": "Brief explanation of the analysis reasoning"
            }
        }
    }

    DIAGNOSIS_SCHEMA = {
        "type": "object",
        "required": ["root_cause", "confidence", "evidence"],
        "properties": {
            "root_cause": {
                "type": "string",
                "description": "Primary root cause identified"
            },
            "contributing_factors": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Secondary contributing factors"
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
                "description": "Confidence in diagnosis (0-1)"
            },
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "description": "Supporting evidence for the diagnosis"
            },
            "alternative_hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "likelihood": {"type": "number"}
                    }
                },
                "description": "Alternative diagnoses with likelihood"
            },
            "verification_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Steps to verify the diagnosis"
            },
            "impact_assessment": {
                "type": "string",
                "description": "Assessment of business impact"
            }
        }
    }

    RECOMMENDATION_SCHEMA = {
        "type": "object",
        "required": ["recommendations", "priority_order"],
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["action", "priority", "expected_impact"],
                    "properties": {
                        "action": {"type": "string"},
                        "priority": {
                            "type": "string",
                            "enum": ["critical", "high", "medium", "low"]
                        },
                        "expected_impact": {"type": "string"},
                        "effort": {
                            "type": "string",
                            "enum": ["low", "medium", "high"]
                        },
                        "dependencies": {
                            "type": "array",
                            "items": {"type": "string"}
                        },
                        "metrics_to_monitor": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    }
                },
                "minItems": 1,
                "maxItems": 10,
                "description": "List of recommendations"
            },
            "priority_order": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "Indices of recommendations in priority order"
            },
            "quick_wins": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Low-effort, high-impact actions"
            },
            "strategic_initiatives": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Long-term strategic recommendations"
            },
            "reasoning": {
                "type": "string",
                "description": "Explanation of prioritization logic"
            }
        }
    }

    CONTENT_ANALYSIS_SCHEMA = {
        "type": "object",
        "required": ["quality_score", "issues", "improvements"],
        "properties": {
            "quality_score": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "description": "Overall content quality score (0-100)"
            },
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "severity": {"type": "string"},
                        "description": {"type": "string"},
                        "location": {"type": "string"}
                    }
                },
                "description": "Identified content issues"
            },
            "improvements": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Suggested improvements"
            },
            "seo_assessment": {
                "type": "object",
                "properties": {
                    "keyword_relevance": {"type": "number"},
                    "readability": {"type": "number"},
                    "structure": {"type": "number"}
                },
                "description": "SEO-specific assessment scores"
            },
            "summary": {
                "type": "string",
                "description": "Brief summary of content analysis"
            }
        }
    }

    @staticmethod
    def get_anomaly_analysis_template() -> PromptTemplate:
        """Get template for analyzing metric anomalies.

        Returns:
            PromptTemplate for anomaly analysis with schema validation.

        Example:
            >>> template = PromptTemplates.get_anomaly_analysis_template()
            >>> prompt = template.format_user_prompt(
            ...     metric_name="clicks",
            ...     current_value=50,
            ...     historical_average=100,
            ...     percent_change=-50.0
            ... )
        """
        system_prompt = """You are an expert SEO analyst specializing in web analytics anomaly detection.
Your task is to analyze metric anomalies and provide actionable insights.

When analyzing anomalies, consider:
1. Seasonal patterns and trends
2. External factors (algorithm updates, market changes)
3. Technical issues (site problems, tracking issues)
4. Content or structural changes
5. Competitive landscape changes

Always provide practical, prioritized recommendations based on the severity and likely cause.
Respond with valid JSON matching the required schema."""

        user_prompt_template = """Analyze the following metric anomaly:

Metric: {metric_name}
Current Value: {current_value}
Historical Average: {historical_average}
Percent Change: {percent_change:.1f}%
Time Period: {time_period}
{additional_context}

Provide a structured analysis including:
1. Severity assessment (critical/high/medium/low)
2. Most likely causes (ranked)
3. Recommended actions to investigate or remediate
4. Confidence level in your analysis
5. Any additional data that would improve the analysis

Respond in JSON format."""

        return PromptTemplate(
            name="anomaly_analysis",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            response_schema=PromptTemplates.ANOMALY_ANALYSIS_SCHEMA,
            required_placeholders=[
                "metric_name", "current_value", "historical_average",
                "percent_change", "time_period"
            ],
            examples=[
                {
                    "input": "Metric: clicks, Current: 50, Historical: 100, Change: -50%",
                    "output": '{"severity": "high", "likely_causes": ["Algorithm update", "Technical issue"], "confidence": 0.75, "recommended_actions": ["Check GSC for manual actions", "Review recent site changes"], "reasoning": "50% drop is significant..."}'
                }
            ]
        )

    @staticmethod
    def get_diagnosis_template() -> PromptTemplate:
        """Get template for diagnosing performance issues.

        Returns:
            PromptTemplate for root cause diagnosis with schema validation.

        Example:
            >>> template = PromptTemplates.get_diagnosis_template()
            >>> prompt = template.format_user_prompt(
            ...     issue_description="Traffic dropped 40%",
            ...     symptoms=["Lower impressions", "Decreased CTR"],
            ...     timeline="Last 7 days",
            ...     affected_pages="Blog section"
            ... )
        """
        system_prompt = """You are an expert SEO diagnostician specializing in identifying root causes of website performance issues.

Your diagnostic approach should:
1. Systematically analyze symptoms and correlations
2. Consider both technical and content-related factors
3. Evaluate internal vs external factors
4. Assess impact on different site sections
5. Provide evidence-based conclusions

Be thorough but practical. Focus on actionable diagnoses.
Respond with valid JSON matching the required schema."""

        user_prompt_template = """Diagnose the following performance issue:

Issue Description: {issue_description}

Symptoms Observed:
{symptoms}

Timeline: {timeline}
Affected Areas: {affected_pages}
{additional_data}

Provide a structured diagnosis including:
1. Primary root cause with confidence level
2. Contributing factors
3. Supporting evidence from the data
4. Alternative hypotheses to consider
5. Steps to verify your diagnosis
6. Impact assessment

Respond in JSON format."""

        return PromptTemplate(
            name="diagnosis",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            response_schema=PromptTemplates.DIAGNOSIS_SCHEMA,
            required_placeholders=[
                "issue_description", "symptoms", "timeline", "affected_pages"
            ],
            examples=[
                {
                    "input": "Issue: 40% traffic drop, Symptoms: Lower impressions, Timeline: 7 days",
                    "output": '{"root_cause": "Google algorithm update", "confidence": 0.8, "evidence": ["Timing coincides with known update", "Pattern matches algorithm impact"], "verification_steps": ["Check algorithm tracker", "Compare against competitors"]}'
                }
            ]
        )

    @staticmethod
    def get_recommendation_template() -> PromptTemplate:
        """Get template for generating strategic recommendations.

        Returns:
            PromptTemplate for recommendations with schema validation.

        Example:
            >>> template = PromptTemplates.get_recommendation_template()
            >>> prompt = template.format_user_prompt(
            ...     context="E-commerce site",
            ...     diagnosis="Content quality issues",
            ...     goals="Increase organic traffic",
            ...     constraints="Limited budget"
            ... )
        """
        system_prompt = """You are an expert SEO strategist providing actionable recommendations.

When creating recommendations:
1. Prioritize by impact and effort (quick wins first)
2. Consider resource constraints
3. Provide specific, measurable actions
4. Include success metrics for each recommendation
5. Identify dependencies between actions

Focus on practical, implementable strategies.
Respond with valid JSON matching the required schema."""

        user_prompt_template = """Generate recommendations based on the following:

Context: {context}
Diagnosis: {diagnosis}
Goals: {goals}
Constraints: {constraints}
{additional_info}

Provide:
1. Prioritized list of recommendations with expected impact
2. Quick wins (low effort, high impact)
3. Strategic initiatives (longer term)
4. Effort estimates for each action
5. Metrics to monitor for success
6. Reasoning for prioritization

Respond in JSON format."""

        return PromptTemplate(
            name="recommendation",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            response_schema=PromptTemplates.RECOMMENDATION_SCHEMA,
            required_placeholders=["context", "diagnosis", "goals", "constraints"],
            examples=[
                {
                    "input": "Context: E-commerce, Diagnosis: Thin content, Goals: More traffic",
                    "output": '{"recommendations": [{"action": "Expand product descriptions", "priority": "high", "expected_impact": "15% traffic increase", "effort": "medium"}], "priority_order": [0], "quick_wins": ["Add FAQ sections"], "strategic_initiatives": ["Content hub creation"]}'
                }
            ]
        )

    @staticmethod
    def get_content_analysis_template() -> PromptTemplate:
        """Get template for analyzing content quality.

        Returns:
            PromptTemplate for content analysis with schema validation.

        Example:
            >>> template = PromptTemplates.get_content_analysis_template()
            >>> prompt = template.format_user_prompt(
            ...     content_type="Blog post",
            ...     content_metrics={"word_count": 500, "readability": 65},
            ...     target_keywords="python tutorial",
            ...     current_performance="Low CTR"
            ... )
        """
        system_prompt = """You are an expert content analyst specializing in SEO and user experience.

When analyzing content:
1. Assess relevance to target keywords and user intent
2. Evaluate readability and structure
3. Check for technical SEO factors
4. Consider E-E-A-T signals (Experience, Expertise, Authoritativeness, Trustworthiness)
5. Identify opportunities for improvement

Provide actionable feedback focused on measurable improvements.
Respond with valid JSON matching the required schema."""

        user_prompt_template = """Analyze the following content:

Content Type: {content_type}
Content Metrics: {content_metrics}
Target Keywords: {target_keywords}
Current Performance: {current_performance}
{content_sample}

Provide:
1. Overall quality score (0-100)
2. Identified issues with severity
3. Specific improvement suggestions
4. SEO assessment (keyword relevance, readability, structure)
5. Summary of findings

Respond in JSON format."""

        return PromptTemplate(
            name="content_analysis",
            system_prompt=system_prompt,
            user_prompt_template=user_prompt_template,
            response_schema=PromptTemplates.CONTENT_ANALYSIS_SCHEMA,
            required_placeholders=[
                "content_type", "content_metrics", "target_keywords",
                "current_performance"
            ]
        )

    @staticmethod
    def get_template_by_name(name: str) -> Optional[PromptTemplate]:
        """Get a template by its name.

        Args:
            name: Template name (anomaly_analysis, diagnosis, recommendation,
                content_analysis)

        Returns:
            PromptTemplate if found, None otherwise.

        Example:
            >>> template = PromptTemplates.get_template_by_name("diagnosis")
            >>> print(template.name)
            diagnosis
        """
        templates = {
            "anomaly_analysis": PromptTemplates.get_anomaly_analysis_template,
            "diagnosis": PromptTemplates.get_diagnosis_template,
            "recommendation": PromptTemplates.get_recommendation_template,
            "content_analysis": PromptTemplates.get_content_analysis_template,
        }

        factory = templates.get(name)
        if factory:
            return factory()
        return None

    @staticmethod
    def list_available_templates() -> List[str]:
        """List all available template names.

        Returns:
            List of template names.

        Example:
            >>> templates = PromptTemplates.list_available_templates()
            >>> print(templates)
            ['anomaly_analysis', 'diagnosis', 'recommendation', 'content_analysis']
        """
        return [
            "anomaly_analysis",
            "diagnosis",
            "recommendation",
            "content_analysis"
        ]

    @staticmethod
    def validate_response(response: Dict[str, Any], schema: Dict[str, Any]) -> tuple:
        """Validate a response against a JSON schema.

        Performs basic validation without requiring jsonschema library.

        Args:
            response: Response dictionary to validate
            schema: JSON schema to validate against

        Returns:
            Tuple of (is_valid, errors_list)

        Example:
            >>> schema = PromptTemplates.ANOMALY_ANALYSIS_SCHEMA
            >>> response = {"severity": "high", "likely_causes": ["Test"]}
            >>> valid, errors = PromptTemplates.validate_response(response, schema)
        """
        errors = []

        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in response:
                errors.append(f"Missing required field: {field}")

        # Check property types
        properties = schema.get("properties", {})
        for field, value in response.items():
            if field not in properties:
                continue

            prop_schema = properties[field]
            expected_type = prop_schema.get("type")

            if expected_type == "string" and not isinstance(value, str):
                errors.append(f"Field '{field}' should be string, got {type(value).__name__}")
            elif expected_type == "number" and not isinstance(value, (int, float)):
                errors.append(f"Field '{field}' should be number, got {type(value).__name__}")
            elif expected_type == "array" and not isinstance(value, list):
                errors.append(f"Field '{field}' should be array, got {type(value).__name__}")
            elif expected_type == "object" and not isinstance(value, dict):
                errors.append(f"Field '{field}' should be object, got {type(value).__name__}")

            # Check enum values
            if "enum" in prop_schema and value not in prop_schema["enum"]:
                errors.append(
                    f"Field '{field}' value '{value}' not in allowed values: {prop_schema['enum']}"
                )

            # Check array bounds
            if expected_type == "array" and isinstance(value, list):
                if "minItems" in prop_schema and len(value) < prop_schema["minItems"]:
                    errors.append(
                        f"Field '{field}' has {len(value)} items, minimum is {prop_schema['minItems']}"
                    )
                if "maxItems" in prop_schema and len(value) > prop_schema["maxItems"]:
                    errors.append(
                        f"Field '{field}' has {len(value)} items, maximum is {prop_schema['maxItems']}"
                    )

            # Check number bounds
            if expected_type == "number" and isinstance(value, (int, float)):
                if "minimum" in prop_schema and value < prop_schema["minimum"]:
                    errors.append(
                        f"Field '{field}' value {value} below minimum {prop_schema['minimum']}"
                    )
                if "maximum" in prop_schema and value > prop_schema["maximum"]:
                    errors.append(
                        f"Field '{field}' value {value} above maximum {prop_schema['maximum']}"
                    )

        is_valid = len(errors) == 0
        return is_valid, errors

    @staticmethod
    def create_json_prompt_suffix() -> str:
        """Create a standard suffix to encourage JSON output.

        Returns:
            String suffix to append to prompts for JSON output.
        """
        return """

IMPORTANT: Respond ONLY with valid JSON. Do not include any text before or after the JSON.
Do not include markdown code blocks. Just output the raw JSON object."""

    @staticmethod
    def get_schema_for_template(template_name: str) -> Optional[Dict[str, Any]]:
        """Get the JSON schema for a named template.

        Args:
            template_name: Name of the template

        Returns:
            JSON schema dict or None if template not found
        """
        schema_map = {
            "anomaly_analysis": PromptTemplates.ANOMALY_ANALYSIS_SCHEMA,
            "diagnosis": PromptTemplates.DIAGNOSIS_SCHEMA,
            "recommendation": PromptTemplates.RECOMMENDATION_SCHEMA,
            "content_analysis": PromptTemplates.CONTENT_ANALYSIS_SCHEMA,
        }
        return schema_map.get(template_name)
