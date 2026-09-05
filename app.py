import json
import time
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Cloud Infrastructure Cost Audit",
    page_icon="☁️",
    layout="wide",
)

st.title("☁️ Cloud Infrastructure Cost Audit Dashboard")
st.caption("AI-powered AWS cost optimization using Apache Airflow, Qdrant Hybrid Search, and LLM.")

API_URL = "http://localhost:8000/audit"
LOCAL_ISSUES_PATH = Path("data/anomalies/detected_issues.json")
LOCAL_CSV_PATH = Path("data/usage_reports/usage_report.csv")


def load_detected_issues() -> list[dict]:
    if LOCAL_ISSUES_PATH.exists():
        try:
            return json.loads(LOCAL_ISSUES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass

    if LOCAL_CSV_PATH.exists():
        from anomaly_detection.detector import run_detection
        from ingestion.usage_parser import parse_usage_report

        res = parse_usage_report(LOCAL_CSV_PATH)
        return run_detection(res.df)

    return [
        {"resource_id": "vol-201", "resource_type": "EBS", "issue_type": "LEGACY_STORAGE", "monthly_cost": 120.0},
        {"resource_id": "i-101", "resource_type": "EC2", "issue_type": "IDLE_RESOURCE", "monthly_cost": 85.0},
        {"resource_id": "vol-202", "resource_type": "EBS", "issue_type": "ORPHANED_STORAGE", "monthly_cost": 18.0},
    ]


issues = load_detected_issues()

with st.sidebar:
    st.header("📊 Infrastructure Health")
    total_spend = sum(item.get("monthly_cost", 0.0) for item in issues)
    st.metric(label="Flagged Resources", value=len(issues))
    st.metric(label="Monthly Spend at Risk", value=f"${total_spend:.2f}")

    st.divider()
    st.header("⚙️ Backend Services")
    st.markdown("- **Airflow UI**: [http://localhost:8080](http://localhost:8080)")
    st.markdown("- **Qdrant DB**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)")
    st.markdown("- **FastAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)")

st.subheader("1. Flagged Cost Issues")
st.write("These resources were detected by the weekly Airflow batch audit using Pandas deterministic rules:")

df_issues = pd.DataFrame(issues)
if not df_issues.empty:
    st.dataframe(
        df_issues.rename(
            columns={
                "resource_id": "Resource ID",
                "resource_type": "Service",
                "issue_type": "Anomaly Detected",
                "monthly_cost": "Monthly Cost ($)",
            }
        ),
        use_container_width=True,
    )

st.subheader("2. Run AI Remediation Audit")

options = {
    f"{item['resource_id']} — {item['resource_type']} ({item['issue_type']}) — ${item['monthly_cost']:.2f}/mo": item
    for item in issues
}

selected_label = st.selectbox("Select a resource to audit:", list(options.keys()))
selected_issue = options[selected_label]
resource_id = selected_issue["resource_id"]

if st.button("🚀 Run AI Audit", type="primary"):
    progress_box = st.empty()
    result_box = st.empty()

    final_result = None

    try:
        with httpx.Client(timeout=30.0) as client:
            with client.stream(
                "POST",
                API_URL,
                json={"resource_id": resource_id},
                headers={"Accept": "text/event-stream"},
            ) as response:
                for line in response.iter_lines():
                    if not line:
                        continue
                    if line.startswith("data:"):
                        payload_str = line[5:].strip()
                        if payload_str.startswith("{"):
                            try:
                                data = json.loads(payload_str)
                                if "audit" in data:
                                    final_result = data["audit"]
                            except Exception:
                                pass
                        else:
                            progress_box.info(f"⏳ **Status**: {payload_str}")

    except Exception:
        # Fallback directly to local modules if FastAPI is offline
        from llm.audit_generator import generate_audit
        from search.hybrid_search import get_hybrid_searcher

        progress_box.info("⏳ **Status**: Searching AWS policies in Qdrant...")
        searcher = get_hybrid_searcher()
        query = f"{selected_issue.get('issue_type', '')} {selected_issue.get('resource_type', '')} cost optimization"
        guidance = searcher.search(query=query, limit=3)

        progress_box.info("⏳ **Status**: Generating recommendation...")
        audit_res = generate_audit(selected_issue, guidance)
        final_result = audit_res.model_dump()

    progress_box.empty()

    if final_result:
        st.success(f"✅ Audit Completed for `{resource_id}`")

        cost = float(final_result.get("monthly_cost", 0.0))
        savings = float(final_result.get("estimated_savings", 0.0))
        annual_savings = savings * 12

        col1, col2, col3 = st.columns(3)
        col1.metric("Current Spend", f"${cost:.2f} / mo")
        col2.metric("Estimated Monthly Savings", f"${savings:.2f} / mo", delta=f"-{(savings / cost * 100) if cost else 0:.0f}%")
        col3.metric("Projected Annual Savings", f"${annual_savings:.2f} / yr")

        st.markdown("### 💡 Recommended Remediation")
        st.info(final_result.get("recommendation", "No recommendation provided."))

        # Generate copyable AWS CLI command
        res_type = final_result.get("resource_type", "")
        issue_type = final_result.get("issue_type", "")

        cli_cmd = ""
        if issue_type == "LEGACY_STORAGE":
            cli_cmd = f"aws ec2 modify-volume --volume-id {resource_id} --volume-type gp3"
        elif issue_type == "ORPHANED_STORAGE":
            cli_cmd = f"# Step 1: Create backup snapshot\naws ec2 create-snapshot --volume-id {resource_id} --description 'Pre-deletion backup'\n\n# Step 2: Delete unattached volume\naws ec2 delete-volume --volume-id {resource_id}"
        elif issue_type == "IDLE_RESOURCE":
            cli_cmd = f"aws ec2 stop-instances --instance-ids {resource_id}"

        if cli_cmd:
            st.markdown("### 🛠️ Action Command (AWS CLI)")
            st.code(cli_cmd, language="bash")

        st.caption(f"📖 Policy Citation: **{final_result.get('source', 'AWS Documentation')}**")
