import json
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
    dag_id="weekly_usage_detector_dag",
    default_args=default_args,
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["usage", "detection"],
)
def weekly_usage_detector_pipeline():

    @task(task_id="detect_cost_issues")
    def detect_issues():
        if "/opt/airflow" not in sys.path:
            sys.path.insert(0, "/opt/airflow")

        from detector import parse_usage_report, run_detection

        s3_bucket = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
        s3_report_key = "usage-reports/usage_report.csv"
        s3_output_key = "anomalies/detected_issues.json"

        base_dir = Path("/opt/airflow") if Path("/opt/airflow").exists() else Path(".")
        local_csv_path = base_dir / "data" / "usage_reports" / "usage_report.csv"
        local_output_path = base_dir / "data" / "detected_issues.json"
        local_output_path.parent.mkdir(parents=True, exist_ok=True)

        aws_key = os.getenv("AWS_ACCESS_KEY_ID")
        if aws_key and not aws_key.startswith("mock"):
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                local_csv_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(s3_bucket, s3_report_key, str(local_csv_path))
            except Exception as e:
                print(f"Notice: S3 report download skipped ({e}). Using local file.")

        if not local_csv_path.exists():
            raise FileNotFoundError(f"Usage report not found at: {local_csv_path}")

        df = parse_usage_report(local_csv_path)
        detected_issues = run_detection(df)

        json_data = json.dumps(detected_issues, indent=2)
        local_output_path.write_text(json_data, encoding="utf-8")

        if aws_key and not aws_key.startswith("mock"):
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                s3.upload_file(str(local_output_path), s3_bucket, s3_output_key)
            except Exception as e:
                print(f"Warning: Could not upload detected issues to S3 ({e}).")

    detect_issues()


weekly_usage_detector_dag = weekly_usage_detector_pipeline()
