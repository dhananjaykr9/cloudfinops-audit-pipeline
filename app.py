import json
import httpx
import streamlit as st

st.title("Cloud Cost Audit Dashboard")

resource = st.selectbox("Select Flagged Resource", ["vol-201", "i-101", "vol-202"])

if st.button("Run AI Audit"):
    status_text = st.empty()
    try:
        with httpx.Client(timeout=30.0) as client:
            with client.stream("POST", "http://localhost:8000/audit", json={"resource_id": resource}) as response:
                for line in response.iter_lines():
                    if line.startswith("data:"):
                        payload = line.replace("data:", "").strip()
                        if payload.startswith("{"):
                            data = json.loads(payload)
                            audit = data.get("audit", {})
                            status_text.empty()
                            st.metric(label="Estimated Monthly Savings", value=f"${audit.get('estimated_savings', 0.0):.2f} / mo")
                            st.success(f"Recommendation: {audit.get('recommendation', '')}")
                            st.info(f"Source: {audit.get('source', '')}")
                        elif payload:
                            status_text.write(payload)
    except Exception as e:
        st.error(f"Could not connect to FastAPI: {e}. Make sure uvicorn is running on port 8000.")
