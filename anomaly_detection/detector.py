"""
Anomaly Detector — Applies simple deterministic rules to the AWS usage report.

Three rules as specified:

  Rule 1 — IDLE_RESOURCE
      EC2 instance where cpu_utilization < 5%

  Rule 2 — ORPHANED_STORAGE
      EBS volume where days_unattached > 14

  Rule 3 — LEGACY_STORAGE
      EBS volume where storage_type == 'gp2' AND storage_size_gb > 500

Output: list of detected issue dicts written to detected_issues.json
"""

import pandas as pd


# ─────────────────────────────────────────────────────────────
# Rule Thresholds (frozen)
# ─────────────────────────────────────────────────────────────

IDLE_CPU_THRESHOLD: float = 5.0       # percent
ORPHAN_DAYS_THRESHOLD: int = 14       # days
LEGACY_SIZE_THRESHOLD: float = 500.0  # GB
LEGACY_STORAGE_TYPE: str = "gp2"


# ─────────────────────────────────────────────────────────────
# Rule 1 — Idle EC2
# ─────────────────────────────────────────────────────────────

def detect_idle_resources(df: pd.DataFrame) -> list[dict]:
    """Flag EC2 instances with cpu_utilization < 5%."""
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

    print(f"[DETECTOR] Rule 1 — IDLE_RESOURCE: {len(anomalies)} flagged")
    return anomalies


# ─────────────────────────────────────────────────────────────
# Rule 2 — Unattached EBS
# ─────────────────────────────────────────────────────────────

def detect_orphaned_storage(df: pd.DataFrame) -> list[dict]:
    """Flag EBS volumes unattached for more than 14 days."""
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

    print(f"[DETECTOR] Rule 2 — ORPHANED_STORAGE: {len(anomalies)} flagged")
    return anomalies


# ─────────────────────────────────────────────────────────────
# Rule 3 — Large gp2 Volume
# ─────────────────────────────────────────────────────────────

def detect_legacy_storage(df: pd.DataFrame) -> list[dict]:
    """Flag gp2 EBS volumes larger than 500 GB."""
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

    print(f"[DETECTOR] Rule 3 — LEGACY_STORAGE: {len(anomalies)} flagged")
    return anomalies


# ─────────────────────────────────────────────────────────────
# Main Entry Point
# ─────────────────────────────────────────────────────────────

def run_detection(df: pd.DataFrame) -> list[dict]:
    """
    Run all three detection rules against the usage report DataFrame.

    Args:
        df: Clean DataFrame from ingestion.usage_parser.

    Returns:
        List of all detected issues.
    """
    print(f"[DETECTOR] Running detection on {len(df)} rows...")
    issues: list[dict] = []
    issues.extend(detect_idle_resources(df))
    issues.extend(detect_orphaned_storage(df))
    issues.extend(detect_legacy_storage(df))
    print(f"[DETECTOR] Total issues detected: {len(issues)}")
    return issues
