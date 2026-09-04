import json
import os
from openai import OpenAI

from api.schemas.audit import FinOpsAudit
from search.hybrid_search import SearchResult


LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

SYSTEM_PROMPT = """You are an AWS Cloud Cost Audit assistant.
Analyze the detected AWS infrastructure cost issue, read the provided AWS guidance documentation, and generate a concise remediation recommendation with estimated monthly savings.

Respond with ONLY a valid JSON object matching this schema:
{
  "resource_id": "<resource_id>",
  "resource_type": "<EC2 or EBS>",
  "issue_type": "<IDLE_RESOURCE or LEGACY_STORAGE or ORPHANED_STORAGE>",
  "monthly_cost": <monthly_cost as float>,
  "recommendation": "<Clear remediation recommendation>",
  "estimated_savings": <estimated savings in USD as float, >= 0>,
  "source": "<source document name>"
}
"""


def _generate_fallback_recommendation(
    issue: dict,
    knowledge_context: list[SearchResult],
) -> FinOpsAudit:
    resource_id = str(issue.get("resource_id", "unknown"))
    resource_type = str(issue.get("resource_type", "EBS"))
    issue_type = str(issue.get("issue_type", "LEGACY_STORAGE"))
    monthly_cost = float(issue.get("monthly_cost", 0.0))

    source_doc = knowledge_context[0].source_document if knowledge_context else "AWS Cost Optimization Guide"
    source_title = source_doc.replace("_", " ").replace(".md", "").title()
    if "Ebs" in source_title:
        source_title = "AWS EBS Cost Optimization Guide"
    elif "Ec2" in source_title:
        source_title = "AWS EC2 Rightsizing Guide"

    if issue_type == "LEGACY_STORAGE":
        savings = round(monthly_cost * 0.20, 2)
        rec = "Consider migrating the gp2 volume to gp3 after validating workload requirements."
    elif issue_type == "ORPHANED_STORAGE":
        savings = round(monthly_cost, 2)
        rec = "Create a snapshot for backup if needed, then delete this unattached EBS volume to eliminate wasted spend."
    elif issue_type == "IDLE_RESOURCE":
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
    resource_id = str(issue.get("resource_id", ""))
    resource_type = str(issue.get("resource_type", ""))
    issue_type = str(issue.get("issue_type", ""))
    monthly_cost = float(issue.get("monthly_cost", 0.0))

    context_text = "\n\n".join([
        f"Document: {r.source_document}\nGuidance: {r.text}\nRecommendation: {r.recommendation}"
        for r in knowledge_context
    ])

    user_prompt = f"""Detected Issue:
Resource ID: {resource_id}
Resource Type: {resource_type}
Issue Type: {issue_type}
Monthly Cost: ${monthly_cost:.2f}

Relevant AWS Guidance:
{context_text}
"""

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_") or api_key == "mock":
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
        return FinOpsAudit.model_validate(parsed)

    except Exception:
        return _generate_fallback_recommendation(issue, knowledge_context)
