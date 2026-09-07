import asyncio, json, os
from pathlib import Path
from typing import Literal
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from openai import OpenAI
from pydantic import BaseModel, Field
from qdrant_store import hybrid_search

app = FastAPI(title="CloudFinOps")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
API_KEY = os.getenv("OPENAI_API_KEY", "")

class FinOpsAudit(BaseModel):
    resource_id: str
    resource_type: str
    issue_type: Literal["IDLE_RESOURCE", "LEGACY_STORAGE", "ORPHANED_STORAGE"]
    monthly_cost: float
    recommendation: str
    estimated_savings: float = Field(ge=0)
    source: str

class AuditRequest(BaseModel):
    resource_id: str


def get_anomaly(res_id: str) -> dict:
    file = Path("data/detected_issues.json")
    if file.exists():
        for item in json.loads(file.read_text(encoding="utf-8")):
            if item.get("resource_id") == res_id:
                return item
    raise HTTPException(status_code=404, detail="Resource not found in detected issues.")


def generate_remediation(issue: dict) -> FinOpsAudit:
    docs = hybrid_search(f"{issue['resource_type']} {issue['issue_type']}")
    context = "\n".join([d.get("text", "") for d in docs])
    cost = float(issue["monthly_cost"])

    if API_KEY and not API_KEY.startswith("your_") and API_KEY != "mock":
        try:
            client = OpenAI(api_key=API_KEY)
            prompt = f"Resource: {issue['resource_id']} ({issue['resource_type']})\nCost: ${cost}\nIssue: {issue['issue_type']}\nGuidance:\n{context}"
            res = client.beta.chat.completions.parse(
                model="gpt-4o-mini", messages=[{"role": "user", "content": prompt}], response_format=FinOpsAudit
            )
            return res.choices[0].message.parsed
        except Exception:
            pass

    # Simple deterministic fallback for local offline testing
    savings = round(cost * 0.20, 2) if issue["issue_type"] == "LEGACY_STORAGE" else (cost if issue["issue_type"] == "ORPHANED_STORAGE" else round(cost * 0.60, 2))
    rec = "Consider migrating the gp2 volume to gp3 after validating workload requirements." if issue["issue_type"] == "LEGACY_STORAGE" else "Delete unattached volume or downsize compute."
    source = "AWS EBS Cost Optimization Guide" if issue["resource_type"] == "EBS" else "AWS EC2 Rightsizing Guide"
    return FinOpsAudit(
        resource_id=issue["resource_id"], resource_type=issue["resource_type"], issue_type=issue["issue_type"],
        monthly_cost=cost, recommendation=rec, estimated_savings=savings, source=source
    )

@app.post("/audit")
def audit(req: AuditRequest):
    return {"status": "success", "audit": generate_remediation(get_anomaly(req.resource_id)).model_dump()}

@app.post("/audit/stream")
async def audit_stream(req: AuditRequest):
    async def sse():
        yield "data: Retrieving detected issue...\n\n"
        await asyncio.sleep(0.2)
        issue = get_anomaly(req.resource_id)
        yield "data: Searching AWS policies in Qdrant...\n\n"
        await asyncio.sleep(0.2)
        res = generate_remediation(issue)
        yield "data: Generating recommendation...\n\n"
        await asyncio.sleep(0.2)
        yield f"data: {json.dumps({'status': 'success', 'audit': res.model_dump()})}\n\n"

    return StreamingResponse(sse(), media_type="text/event-stream")
