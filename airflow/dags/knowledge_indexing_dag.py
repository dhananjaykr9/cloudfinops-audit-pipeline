import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

for path_dir in ("/opt/airflow", str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2])):
    if path_dir not in sys.path:
        sys.path.insert(0, path_dir)

from airflow.decorators import dag, task
import boto3
from botocore.exceptions import ClientError


default_args = {
    "owner": "airflow",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=2),
}


@dag(
    dag_id="knowledge_indexing_dag",
    default_args=default_args,
    schedule=None,
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["knowledge", "qdrant"],
)
def knowledge_indexing_pipeline():

    @task(task_id="index_aws_cost_documents")
    def index_documents():
        if "/opt/airflow" not in sys.path:
            sys.path.insert(0, "/opt/airflow")

        from ingestion.document_parser import parse_documents_from_paths
        from qdrant.vector_store import get_vector_store

        s3_bucket = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
        s3_prefix = "knowledge/aws-cost-guides/"
        local_doc_dir = Path("/opt/airflow/data/documents") if Path("/opt/airflow").exists() else Path("data/documents")

        doc_paths: list[Path] = []

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
            except ClientError as e:
                print(f"Notice: S3 download skipped ({e}). Using local documents.")

        if local_doc_dir.exists():
            for ext in ("*.md", "*.txt", "*.pdf"):
                doc_paths.extend(local_doc_dir.glob(ext))

        if not doc_paths:
            print("No documents found to index.")
            return

        chunks = parse_documents_from_paths(doc_paths)
        vs = get_vector_store()
        count = vs.upsert_chunks(chunks)
        print(f"Successfully indexed {count} chunks into Qdrant.")

    index_documents()


knowledge_indexing_dag = knowledge_indexing_pipeline()
