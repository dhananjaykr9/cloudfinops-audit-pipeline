import pandas as pd


IDLE_CPU_THRESHOLD = 5.0
ORPHAN_DAYS_THRESHOLD = 14
LEGACY_SIZE_THRESHOLD = 500.0
LEGACY_STORAGE_TYPE = "gp2"


def detect_idle_resources(df: pd.DataFrame) -> list[dict]:
    mask = (
        (df["resource_type"] == "EC2") &
        df["cpu_utilization"].notna() &
        (df["cpu_utilization"] < IDLE_CPU_THRESHOLD)
    )

    anomalies = []
    for _, row in df[mask].iterrows():
        anomalies.append({
            "resource_id": row["resource_id"],
            "resource_type": "EC2",
            "issue_type": "IDLE_RESOURCE",
            "monthly_cost": float(row["monthly_cost"]),
        })

    return anomalies


def detect_orphaned_storage(df: pd.DataFrame) -> list[dict]:
    mask = (
        (df["resource_type"] == "EBS") &
        df["days_unattached"].notna() &
        (df["days_unattached"] > ORPHAN_DAYS_THRESHOLD)
    )

    anomalies = []
    for _, row in df[mask].iterrows():
        anomalies.append({
            "resource_id": row["resource_id"],
            "resource_type": "EBS",
            "issue_type": "ORPHANED_STORAGE",
            "monthly_cost": float(row["monthly_cost"]),
        })

    return anomalies


def detect_legacy_storage(df: pd.DataFrame) -> list[dict]:
    mask = (
        (df["resource_type"] == "EBS") &
        (df["storage_type"].str.lower() == LEGACY_STORAGE_TYPE) &
        df["storage_size_gb"].notna() &
        (df["storage_size_gb"] > LEGACY_SIZE_THRESHOLD)
    )

    anomalies = []
    for _, row in df[mask].iterrows():
        anomalies.append({
            "resource_id": row["resource_id"],
            "resource_type": "EBS",
            "issue_type": "LEGACY_STORAGE",
            "monthly_cost": float(row["monthly_cost"]),
        })

    return anomalies


def run_detection(df: pd.DataFrame) -> list[dict]:
    issues: list[dict] = []
    issues.extend(detect_idle_resources(df))
    issues.extend(detect_orphaned_storage(df))
    issues.extend(detect_legacy_storage(df))
    return issues
