import asyncio
import json
import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse

from api.schemas.audit import AuditRequest, FinOpsAudit
from llm.audit_generator import generate_audit
from search.hybrid_search import get_hybrid_searcher


router = APIRouter()

S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
S3_ANOMALIES_KEY = "anomalies/detected_issues.json"
LOCAL_ANOMALIES_PATH = Path("data/anomalies/detected_issues.json")


def _read_detected_issues() -> list[dict]:
    aws_key = os.getenv("AWS_ACCESS_KEY_ID")
    if aws_key and not aws_key.startswith("mock"):
        try:
            s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
            response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=S3_ANOMALIES_KEY)
            return json.loads(response["Body"].read().decode("utf-8"))
        except ClientError:
            pass

    if LOCAL_ANOMALIES_PATH.exists():
        try:
            return json.loads(LOCAL_ANOMALIES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    return []


@router.post("/audit")
async def audit(request: AuditRequest):
    resource_id = request.resource_id

    async def sse_stream():
        yield {"data": "Retrieving detected issue..."}
        await asyncio.sleep(0.3)

        issues = _read_detected_issues()
        issue = next((item for item in issues if item.get("resource_id") == resource_id), None)

        if not issue:
            yield {"data": f"Error: Resource '{resource_id}' not found in detected issues."}
            return

        yield {"data": "Searching AWS policies..."}
        await asyncio.sleep(0.3)

        query = f"{issue.get('issue_type', '')} {issue.get('resource_type', '')} cost optimization"
        guidance = get_hybrid_searcher().search(query=query, limit=3)

        yield {"data": "Generating recommendation..."}
        await asyncio.sleep(0.3)

        audit_result: FinOpsAudit = generate_audit(issue, guidance)

        yield {"data": "Validating response..."}
        await asyncio.sleep(0.2)

        yield {"data": "Audit completed."}

        response_payload = {
            "status": "success",
            "audit": audit_result.model_dump(),
        }
        yield {"data": json.dumps(response_payload)}

    return EventSourceResponse(sse_stream())
