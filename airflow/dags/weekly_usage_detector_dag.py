"""
Weekly Usage Detector DAG — Analyzes AWS usage report and detects cost issues.

Uses Airflow TaskFlow API (@dag and @task decorators).
"""

import json
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
    dag_id="weekly_usage_detector_dag",
    default_args=default_args,
    description="Analyze weekly AWS usage report with Pandas rules and generate detected_issues.json",
    schedule="@weekly",
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=["finops", "usage", "detection"],
)
def weekly_usage_detector_pipeline():

    @task(task_id="detect_cost_issues")
    def detect_issues():
        """
        1. Read usage report CSV from S3 (or local data/usage_reports/ folder).
        2. Load CSV using Pandas via usage_parser.
        3. Apply cost detection rules via detector.
        4. Create detected_issues.json.
        5. Upload result to S3 (and save locally).
        """
        import sys
        if "/opt/airflow" not in sys.path:
            sys.path.insert(0, "/opt/airflow")

        from ingestion.usage_parser import parse_usage_report
        from anomaly_detection.detector import run_detection

        s3_bucket = os.getenv("S3_BUCKET_NAME", "cloudfinops-data")
        s3_report_key = "usage-reports/usage_report.csv"
        s3_output_key = "anomalies/detected_issues.json"

        base_dir = Path("/opt/airflow") if Path("/opt/airflow").exists() else Path(".")
        local_csv_path = base_dir / "data" / "usage_reports" / "usage_report.csv"
        local_out_dir = base_dir / "data" / "anomalies"
        local_out_dir.mkdir(parents=True, exist_ok=True)
        local_output_path = local_out_dir / "detected_issues.json"

        # 1. Attempt to download the latest report from S3
        aws_key = os.getenv("AWS_ACCESS_KEY_ID")
        if aws_key and not aws_key.startswith("mock"):
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                local_csv_path.parent.mkdir(parents=True, exist_ok=True)
                s3.download_file(s3_bucket, s3_report_key, str(local_csv_path))
                print(f"[DAG] Downloaded latest usage report from s3://{s3_bucket}/{s3_report_key}")
            except ClientError as e:
                print(f"[DAG] Notice: Could not download usage report from S3 ({e}). Using local file.")

        if not local_csv_path.exists():
            raise FileNotFoundError(f"[DAG] Usage report not found at: {local_csv_path}")

        # 2. Parse CSV using Pandas
        print(f"[DAG] Reading usage report from: {local_csv_path}")
        parse_result = parse_usage_report(local_csv_path)

        # 3. Apply cost detection rules
        print(f"[DAG] Running cost detection rules on {len(parse_result.df)} rows...")
        detected_issues = run_detection(parse_result.df)

        # 4. Create detected_issues.json
        json_data = json.dumps(detected_issues, indent=2)
        local_output_path.write_text(json_data, encoding="utf-8")
        print(f"[DAG] Wrote {len(detected_issues)} issues to: {local_output_path}")

        # 5. Upload result to S3
        if aws_key and not aws_key.startswith("mock"):
            try:
                s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
                s3.upload_file(str(local_output_path), s3_bucket, s3_output_key)
                print(f"[DAG] Uploaded detected issues to s3://{s3_bucket}/{s3_output_key}")
            except ClientError as e:
                print(f"[DAG] Warning: Could not upload detected issues to S3 ({e}).")

    detect_issues()


weekly_usage_detector_dag = weekly_usage_detector_pipeline()
