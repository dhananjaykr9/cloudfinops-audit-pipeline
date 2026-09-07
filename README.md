# Cloud Infrastructure Cost Audit Pipeline

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Apache Airflow](https://img.shields.io/badge/Apache_Airflow-3.3.0-017CEE?style=for-the-badge&logo=apache-airflow&logoColor=white)](https://airflow.apache.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Hybrid_Search-DC382D?style=for-the-badge&logo=qdrant&logoColor=white)](https://qdrant.tech/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

An end-to-end, automated Cloud FinOps solution designed to detect AWS infrastructure cost leaks and synthesize policy-backed remediation recommendations using **Hybrid Vector Search (Dense + Sparse RAG)** and Large Language Models.

---

## 💡 Executive Overview

Cloud bills grow unpredictably when unattached storage and idle compute resources are left unmonitored. Feeding massive, raw AWS billing logs (often 100,000+ rows) directly into an LLM is impractical due to high token costs, latency, context limitations, and numerical hallucinations.

This pipeline introduces a **decoupled, two-stage architecture**:
1. **Deterministic Batch Auditing**: Apache Airflow schedules Pandas-driven detection rules over AWS Cost & Usage Reports (CUR) to mathematically flag cost anomalies for pennies in milliseconds.
2. **Context-Aware AI Remediation**: FastAPI coordinates on-demand audits using Qdrant Hybrid Search (Reciprocal Rank Fusion) across official AWS cost guides, utilizing OpenAI `gpt-4o-mini` and Pydantic v2 to generate validated remediation steps and dollar savings.
3. **Interactive FinOps Dashboard**: A pure-Python Streamlit interface enables engineering leads and financial stakeholders to trigger audits and monitor real-time savings.

---

## 🏗️ System Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                       1. BATCH DETECTION (Weekly)                           │
│                                                                             │
│   AWS Usage Report (CSV)  ──►  Apache Airflow DAG  ──►  Pandas Rules        │
│                                (weekly_usage_dag)        • Idle EC2 (<5%)   │
│                                                          • Orphaned EBS     │
│                                                          • gp2 Storage      │
│                                                                 │           │
│                                                                 ▼           │
│                                                      detected_issues.json   │
└─────────────────────────────────────────────────────────────────┼───────────┘
                                                                  │
                                                      Select Anomaly (Resource ID)
                                                                  │
┌──────────────────────────────────────┐                          ▼
│     2. HYBRID KNOWLEDGE RAG          │        ┌─────────────────────────────┐
│                                      │        │  3. AI REMEDIATION & API    │
│  AWS Cost Whitepapers (Markdown/PDF) │        │                             │
│                 │                    │        │  FastAPI (/audit/stream)    │
│                 ▼                    │        │              │              │
│  Knowledge Indexing DAG (Airflow)    │        │              ▼              │
│                 │                    │        │  Qdrant RRF Hybrid Search   │
│                 ▼                    │        │  (Dense bge-small + BM25)   │
│  FastEmbed (Dense + Sparse BM25)     │        │              │              │
│                 │                    │        │              ▼              │
│                 ▼                    │        │  OpenAI gpt-4o-mini         │
│  Qdrant Vector Database  ────────────┼───────►│  (Remediation Synthesis)    │
│  (Collection: aws_finops_knowledge)  │        │              │              │
└──────────────────────────────────────┘        │              ▼              │
                                                │  Pydantic v2 Schema Check   │
                                                │  (Savings >= $0 Validation) │
                                                │              │              │
                                                │              ▼              │
                                                │  Server-Sent Events (SSE)   │
                                                └──────────────┬──────────────┘
                                                               │
                                                       Live Stream Updates
                                                               │
                                                               ▼
                                                ┌─────────────────────────────┐
                                                │  4. STREAMLIT DASHBOARD     │
                                                │  • Pick flagged resource    │
                                                │  • Watch real-time progress │
                                                │  • View estimated savings   │
                                                └─────────────────────────────┘
```

### How It Works (In 4 Simple Steps):
1. **Batch Cost Detection (Airflow)**: Reads raw AWS usage CSVs and evaluates deterministic threshold rules with Pandas (idle EC2, orphaned EBS, legacy gp2 storage). Saves flagged anomalies into `detected_issues.json` without burning LLM tokens.
2. **Knowledge Ingestion (Airflow + Qdrant)**: Official AWS cost optimization documents are chunked and converted into dense vectors (semantic meaning) and sparse BM25 vectors (exact technical keywords like `gp2`, `t3.large`), stored in Qdrant.
3. **AI Remediation Service (FastAPI)**: When an audit is triggered for a resource, FastAPI queries Qdrant using Reciprocal Rank Fusion (RRF), passes the relevant guidance to `gpt-4o-mini`, and validates the structured output via Pydantic v2.
4. **Interactive Dashboard (Streamlit)**: Users pick any flagged resource, watch real-time audit progress streamed via Server-Sent Events (SSE), and view verified monthly savings recommendations.

---

## ✨ Key Features

* **⚡ Two-Stage Decoupled Auditing**: High-speed mathematical detection using Pandas combined with surgical LLM remediation synthesis.
* **🔍 Hybrid Vector Search (Dense + Sparse BM25)**: Matches semantic concepts while preserving exact technical identifiers (e.g., `gp2`, `gp3`, `t3.large`, `EBS`) using Qdrant's Reciprocal Rank Fusion (RRF).
* **📦 Lightweight ONNX Embeddings**: Powered by FastEmbed (`bge-small-en-v1.5` and `bm25`), cutting container memory footprints by over 500 MB compared to standard PyTorch setups.
* **🛡️ Pydantic v2 Schema Enforcement**: Enforces non-negative savings constraints and strict JSON data typing to prevent downstream dashboard failures.
* **📡 Real-Time SSE Progress Streaming**: Delivers live status milestones (`Searching AWS policies...`, `Generating recommendation...`) over HTTP.
* **🖥️ 100% Pure-Python Interactive Dashboard**: Built with Streamlit for seamless exploration of flagged resources and savings metrics.

---

## 🛠️ Tech Stack

| Component | Technology | Description |
|---|---|---|
| **Core Runtime** | Python 3.11+ | Primary programming language |
| **User Interface** | Streamlit | Pure-Python interactive cost audit dashboard |
| **Data Processing** | Pandas | High-performance tabular metric analysis |
| **Orchestration** | Apache Airflow 3.3.0 | Celery-backed batch pipeline scheduling |
| **API Framework** | FastAPI & Uvicorn | Asynchronous REST microservice with SSE streaming |
| **Data Validation** | Pydantic v2 | Strict schema enforcement and output contracts |
| **Vector Database** | Qdrant | Hybrid search engine supporting dense and sparse vectors |
| **Embedding Models** | FastEmbed (ONNX) | `BAAI/bge-small-en-v1.5` (Dense) & `Qdrant/bm25` (Sparse) |
| **LLM Inference** | OpenAI `gpt-4o-mini` | Low-latency remediation synthesis |
| **Containerization** | Docker & Docker Compose | Multi-service orchestration (Airflow, Postgres, Redis, Qdrant) |

---

## 📂 Repository Structure

```text
cloudfinops-audit-pipeline/
│
├── airflow/
│   ├── dags/
│   │   ├── knowledge_indexing_dag.py     # Indexes AWS cost whitepapers into Qdrant
│   │   └── weekly_usage_detector_dag.py  # Evaluates weekly usage logs against rules
│   ├── logs/                             # Airflow execution logs
│   ├── plugins/                          # Airflow plugins
│   └── config/                           # Airflow configuration
│
├── data/
│   ├── aws_guidance/                     # Official AWS cost-optimization whitepapers
│   │   ├── ebs_cost_optimization.md
│   │   └── ec2_rightsizing_guide.md
│   ├── usage_reports/                    # Simulated AWS Cost & Usage Reports (CUR)
│   │   └── usage_report.csv
│   └── detected_issues.json              # Output of detected cost anomalies
│
├── screenshots/                          # Architecture and UI visual assets
├── detector.py                           # Deterministic Pandas rule definitions & CSV parsing
├── qdrant_store.py                       # FastEmbed, Qdrant vector store, chunking & RRF
├── main.py                               # FastAPI application entrypoint with /audit & /audit/stream
├── app.py                                # Streamlit dashboard application
├── docker-compose.yaml                   # Container infrastructure stack
├── requirements.txt                      # Project dependencies
└── README.md                             # Project documentation
```

---

## 📏 Deterministic Cost Detection Rules

The weekly detector evaluates usage reports using three deterministic threshold rules:

1. **Rule 1 — Idle Compute (`IDLE_RESOURCE`)**:
   - `cpu_utilization < 5%`
   - *Flags EC2 instances running with negligible CPU utilization.*
2. **Rule 2 — Orphaned Storage (`ORPHANED_STORAGE`)**:
   - `days_unattached > 14 days`
   - *Flags unattached EBS volumes continuing to incur storage charges.*
3. **Rule 3 — Oversized Legacy Storage (`LEGACY_STORAGE`)**:
   - `storage_type == 'gp2' and storage_size_gb > 500 GB`
   - *Flags legacy gp2 volumes eligible for ~20% cost reduction by migrating to gp3.*

Flagged anomalies are serialized to `data/detected_issues.json`:
```json
[
  {
    "resource_id": "i-101",
    "resource_type": "EC2",
    "issue_type": "IDLE_RESOURCE",
    "monthly_cost": 85.0
  },
  {
    "resource_id": "vol-201",
    "resource_type": "EBS",
    "issue_type": "LEGACY_STORAGE",
    "monthly_cost": 120.0
  }
]
```

---

## 🔌 API Specification & SSE Streaming

### Request
```http
POST /audit HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "resource_id": "vol-201"
}
```

### Real-time Event Stream (`text/event-stream`)
```text
event: message
data: Retrieving detected issue...

event: message
data: Searching AWS policies...

event: message
data: Generating recommendation...

event: message
data: Validating response...

event: message
data: Audit completed.

event: result
data: {
  "status": "success",
  "audit": {
    "resource_id": "vol-201",
    "resource_type": "EBS",
    "issue_type": "LEGACY_STORAGE",
    "monthly_cost": 120.0,
    "recommendation": "Migrate volume from gp2 to gp3 to achieve equivalent performance at 20% lower baseline cost.",
    "estimated_savings": 24.0,
    "source": "AWS EBS Cost Optimization Guide"
  }
}
```

---

## 🚀 Getting Started

### 1. Prerequisites
- Docker & Docker Compose
- Python 3.11+
- OpenAI API Key (optional — system includes deterministic fallback for offline testing)

### 2. Environment Configuration & Dependencies
Clone the repository, configure the environment, and install dependencies using **`uv`** (recommended) or standard `pip`:

**Using `uv` (Recommended — Fastest):**
```bash
uv pip install -r requirements.txt
cp .env.example .env
```

**Or using standard `venv` & `pip`:**
```bash
python -m venv .venv
# On Windows: .venv\Scripts\activate
# On Linux/macOS: source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
```

### 3. Launch Docker Infrastructure
Start the background services (Apache Airflow, PostgreSQL, Redis, Qdrant):
```bash
docker compose up -d
```
- **Apache Airflow UI**: [http://localhost:8080](http://localhost:8080) (`airflow` / `airflow`)
- **Qdrant Vector Dashboard**: [http://localhost:6333/dashboard](http://localhost:6333/dashboard)

### 4. Run Batch Pipelines via Apache Airflow UI
Open the Airflow Web UI at **[http://localhost:8080](http://localhost:8080)** (login: `airflow` / `airflow`) and trigger the DAGs:
1. **`knowledge_indexing_dag`**: Ingests AWS cost guides, generates dense + BM25 embeddings, and indexes them into Qdrant.
2. **`weekly_usage_detector_dag`**: Evaluates the AWS usage report using deterministic Pandas rules and outputs flagged anomalies to `data/detected_issues.json`.

### 5. Start the FastAPI Microservice
In a new terminal, start the API server:
```bash
# Using uv:
uv run python -m uvicorn main:app --reload --port 8000

# Or with activated virtual environment:
python -m uvicorn main:app --reload --port 8000
```
- **Interactive Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

*(Optional quick cURL audit test)*:
```bash
curl -X POST http://localhost:8000/audit -H "Content-Type: application/json" -d "{\"resource_id\": \"vol-201\"}"
```

### 6. Launch the Streamlit Dashboard
In another terminal, launch the interactive UI:
```bash
# Using uv:
uv run python -m streamlit run app.py

# Or with activated virtual environment:
python -m streamlit run app.py
```
- **Web Dashboard**: [http://localhost:8501](http://localhost:8501)
- Select a flagged resource (e.g. `vol-201`, `i-101`, `vol-202`) and click **"Run AI Audit"** to view real-time streaming progress and savings KPI cards.

---

## 📸 Screenshots & Artifacts

Visual captures of the pipeline runs, dashboards, and API interfaces are stored in the [`screenshots/`](screenshots/) directory:

- **`screenshots/streamlit_dashboard.png`**: Interactive FinOps audit dashboard with real-time SSE progress milestones and monthly savings metrics.
- **`screenshots/airflow_dags.png`**: Apache Airflow DAGs overview showing scheduled batch pipelines.
- **`screenshots/airflow_knowledge_dag.png`**: Execution graph and task details for the AWS documentation indexing DAG.
- **`screenshots/airflow_detector_dag.png`**: Execution graph and task details for the weekly usage detector DAG.
- **`screenshots/qdrant_dashboard.png`**: Qdrant web dashboard showing hybrid dense (384-dim) and sparse (BM25) vector collections.
- **`screenshots/fastapi_docs.png`**: Interactive Swagger OpenAPI 3.1 documentation for `/audit` and `/audit/stream`.


