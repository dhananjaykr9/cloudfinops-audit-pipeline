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

        from qdrant_store import index_documents as run_indexing

        s3_bucket = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
        s3_prefix = "knowledge/aws-cost-guides/"
        local_doc_dir = Path("/opt/airflow/data/aws_guidance") if Path("/opt/airflow").exists() else Path("data/aws_guidance")
        local_doc_dir.mkdir(parents=True, exist_ok=True)

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
            except Exception as e:
                print(f"Notice: S3 download skipped ({e}). Using local documents.")

        count = run_indexing(docs_dir=local_doc_dir)
        print(f"Successfully indexed {count} chunks into Qdrant.")

    index_documents()


knowledge_indexing_dag = knowledge_indexing_pipeline()
