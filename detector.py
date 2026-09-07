import json
from pathlib import Path
import pandas as pd


def parse_usage_report(csv_path: str = "data/usage_reports/usage_report.csv") -> pd.DataFrame:
    """Reads AWS billing CSV and strips column whitespaces."""
    df = pd.read_csv(csv_path)
    df.columns = df.columns.str.strip()
    return df


def run_detection(df: pd.DataFrame) -> list[dict]:
    """Applies 3 deterministic FinOps threshold rules over the usage dataframe."""
    anomalies = []

    for _, row in df.iterrows():
        res_id = str(row["resource_id"]).strip()
        res_type = str(row["resource_type"]).strip().upper()
        cost = float(row.get("monthly_cost", 0.0))

        # 1. Idle EC2 (CPU < 5%)
        if res_type == "EC2" and row.get("cpu_utilization", 100) < 5.0:
            anomalies.append({"resource_id": res_id, "resource_type": "EC2", "issue_type": "IDLE_RESOURCE", "monthly_cost": cost})

        # 2. Orphaned EBS (> 14 days unattached)
        elif res_type == "EBS" and row.get("days_unattached", 0) > 14:
            anomalies.append({"resource_id": res_id, "resource_type": "EBS", "issue_type": "ORPHANED_STORAGE", "monthly_cost": cost})

        # 3. Large legacy gp2 volume (> 500 GB)
        elif res_type == "EBS" and str(row.get("storage_type", "")).lower() == "gp2" and row.get("storage_size_gb", 0) > 500:
            anomalies.append({"resource_id": res_id, "resource_type": "EBS", "issue_type": "LEGACY_STORAGE", "monthly_cost": cost})

    return anomalies


def run_pipeline(
    csv_path: str = "data/usage_reports/usage_report.csv",
    output_path: str = "data/detected_issues.json"
) -> list[dict]:
    """Executes full detection pipeline and writes output JSON."""
    df = parse_usage_report(csv_path)
    issues = run_detection(df)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(issues, f, indent=2)
    return issues


if __name__ == "__main__":
    print("Detected anomalies:", run_pipeline())
