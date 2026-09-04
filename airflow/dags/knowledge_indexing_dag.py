"""
Knowledge Indexing DAG — Processes AWS cost-optimization documents and updates Qdrant.

Uses Airflow TaskFlow API (@dag and @task decorators).
"""

import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Ensure /opt/airflow is in sys.path
for path_dir in ("/opt/airflow", str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])):
    if path_dir not in sys.path:
        sys.path.insert(0, path_dir)

from airflow.decorators import dag, task

import boto3
from botocore.exceptions import ClientError


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="knowledge_indexing_dag",
    default_args=default_args,
    description="Index AWS cost optimization documents into Qdrant using dense and sparse embeddings",
    schedule=None,  # Triggered on-demand when docs are added/updated
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["finops", "knowledge", "qdrant"],
)
def knowledge_indexing_pipeline():

    @task(task_id="index_aws_cost_documents")
    def index_documents():
        """
        1. Read AWS cost documents from S3 or local documents folder.
        2. Extract text and split into chunks.
        3. Generate dense + sparse embeddings and store into Qdrant.
        """
        import sys
        if "/opt/airflow" not in sys.path:
            sys.path.insert(0, "/opt/airflow")

        from ingestion.document_parser import parse_documents_from_paths
        from qdrant.vector_store import get_vector_store

        s3_bucket = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
        s3_prefix = "knowledge/aws-cost-guides/"
        local_doc_dir = Path("/opt/airflow/data/documents") if Path("/opt/airflow").exists() else Path("data/documents")

        doc_paths: list[Path] = []

        # 1. Attempt to download any documents from S3
        aws_key = os.getenv("AWS_ACCESS_KEY_ID")
        if aws_key and not aws_key.startswith("mock"):
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                response = s3.list_objects_v2(Bucket=s3_bucket, Prefix=s3_prefix)
                for item in response.get("Contents", []):
                    key = item["Key"]
                    if key.endswith("/") or not (key.endswith(".md") or key.endswith(".txt") or key.endswith(".pdf")):
                        continue
                    filename = Path(key).name
                    dest = local_doc_dir / filename
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    s3.download_file(s3_bucket, key, str(dest))
                    print(f"[DAG] Downloaded from S3: {key} -> {dest}")
            except ClientError as e:
                print(f"[DAG] Notice: Could not download from S3 ({e}). Using local documents.")

        # 2. Collect local documents
        if local_doc_dir.exists():
            for ext in ("*.md", "*.txt", "*.pdf"):
                doc_paths.extend(local_doc_dir.glob(ext))

        print(f"[DAG] Found {len(doc_paths)} documents to index: {[p.name for p in doc_paths]}")

        if not doc_paths:
            print("[DAG] No documents found to index.")
            return

        # 3. Parse and chunk
        chunks = parse_documents_from_paths(doc_paths)
        print(f"[DAG] Created {len(chunks)} chunks.")

        # 4. Upsert into Qdrant
        vs = get_vector_store()
        count = vs.upsert_chunks(chunks)
        print(f"[DAG] Successfully indexed {count} chunks into Qdrant.")

    index_documents()


knowledge_indexing_dag = knowledge_indexing_pipeline()
