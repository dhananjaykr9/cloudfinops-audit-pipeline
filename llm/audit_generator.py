"""
Audit Generator — Synthesizes remediation recommendations using an LLM + retrieved knowledge.

Follows the RAG pattern:
    1. Receives the detected issue (resource_id, resource_type, issue_type, monthly_cost)
    2. Receives relevant AWS guidance retrieved from Qdrant Hybrid Search
    3. Calls LLM (gpt-4o-mini) to generate recommendation and estimated savings
    4. Validates output using Pydantic v2 (FinOpsAudit)
"""

import json
import os
import re
from typing import Optional

from openai import OpenAI

from api.schemas.audit import FinOpsAudit
from search.hybrid_search import SearchResult


LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")


SYSTEM_PROMPT = """You are an AWS Cloud FinOps expert assistant.
Your job is to analyze a detected AWS infrastructure cost issue, read the provided AWS guidance documentation, and generate a concise remediation recommendation with estimated monthly savings.

You must respond with ONLY a valid JSON object matching this schema:
{
  "resource_id": "<resource_id>",
  "resource_type": "<EC2 or EBS>",
  "issue_type": "<IDLE_RESOURCE or LEGACY_STORAGE or ORPHANED_STORAGE>",
  "monthly_cost": <monthly_cost as float>,
  "recommendation": "<Clear, actionable remediation recommendation>",
  "estimated_savings": <estimated monthly savings in USD as float, must be >= 0>,
  "source": "<source document name or guide title>"
}
"""


def _generate_fallback_recommendation(
    issue: dict,
    knowledge_context: list[SearchResult],
) -> FinOpsAudit:
    """Deterministic fallback when OpenAI API key is not configured or offline."""
    resource_id = str(issue.get("resource_id", "unknown"))
    resource_type = str(issue.get("resource_type", "EBS"))
    issue_type = str(issue.get("issue_type", "LEGACY_STORAGE"))
    monthly_cost = float(issue.get("monthly_cost", 0.0))

    source_doc = knowledge_context[0].source_document if knowledge_context else "AWS Cost Optimization Guide"
    # Clean up filename if needed
    source_title = source_doc.replace("_", " ").replace(".md", "").title()
    if "Ebs" in source_title:
        source_title = "AWS EBS Cost Optimization Guide"
    elif "Ec2" in source_title:
        source_title = "AWS EC2 Rightsizing Guide"

    if issue_type == "LEGACY_STORAGE":
        # gp2 to gp3 saves ~20%
        savings = round(monthly_cost * 0.20, 2)
        rec = "Consider migrating the gp2 volume to gp3 after validating workload requirements."
    elif issue_type == "ORPHANED_STORAGE":
        # Unattached volume deletion saves 100%
        savings = round(monthly_cost, 2)
        rec = "Create a snapshot for backup if needed, then delete this unattached EBS volume to eliminate wasted spend."
    elif issue_type == "IDLE_RESOURCE":
        # Idle EC2: stopping or downsizing saves ~50-100%
        savings = round(monthly_cost * 0.60, 2)
        rec = "Review instance utilization. Consider stopping the instance or downsizing to a smaller instance family."
    else:
        savings = 0.0
        rec = knowledge_context[0].recommendation if knowledge_context else "Review resource configuration for cost optimization."

    return FinOpsAudit(
        resource_id=resource_id,
        resource_type=resource_type,
        issue_type=issue_type,  # type: ignore
        monthly_cost=monthly_cost,
        recommendation=rec,
        estimated_savings=savings,
        source=source_title,
    )


def generate_audit(
    issue: dict,
    knowledge_context: list[SearchResult],
) -> FinOpsAudit:
    """
    Generate and validate a FinOps audit recommendation.

    Args:
        issue: Detected issue dict (resource_id, resource_type, issue_type, monthly_cost)
        knowledge_context: List of SearchResult objects from Qdrant hybrid search

    Returns:
        Validated FinOpsAudit Pydantic v2 instance.
    """
    resource_id = str(issue.get("resource_id", ""))
    resource_type = str(issue.get("resource_type", ""))
    issue_type = str(issue.get("issue_type", ""))
    monthly_cost = float(issue.get("monthly_cost", 0.0))

    # Format retrieved context
    context_text = "\n\n".join([
        f"Document: {r.source_document}\nGuidance: {r.text}\nRecommendation: {r.recommendation}"
        for r in knowledge_context
    ])

    user_prompt = f"""Detected Issue:
Resource ID: {resource_id}
Resource Type: {resource_type}
Issue Type: {issue_type}
Monthly Cost: ${monthly_cost:.2f}

Relevant AWS Guidance from Knowledge Base:
{context_text}

Provide the remediation recommendation in the required JSON format.
"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key == "mock":
        print("[LLM] No valid OPENAI_API_KEY configured. Using knowledge-grounded generator.")
        return _generate_fallback_recommendation(issue, knowledge_context)

    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model=LLM_MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)

        # Validate with Pydantic v2
        audit = FinOpsAudit.model_validate(parsed)
        print(f"[LLM] Successfully generated and validated audit for {resource_id}")
        return audit

    except Exception as e:
        print(f"[LLM] OpenAI invocation failed: {e}. Falling back to knowledge-grounded generator.")
        return _generate_fallback_recommendation(issue, knowledge_context)
