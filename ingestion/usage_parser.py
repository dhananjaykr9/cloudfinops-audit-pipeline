"""
Usage Parser — Loads and validates the AWS usage report CSV.

Produces a clean Pandas DataFrame ready for cost issue detection.

Expected CSV columns:
    resource_id      - Unique resource identifier (e.g. i-101, vol-201)
    resource_type    - EC2 | EBS
    instance_type    - EC2 instance type (e.g. t3.large), null for EBS
    monthly_cost     - Current monthly cost in USD (float)
    cpu_utilization  - Average CPU percentage (float, null for EBS)
    storage_type     - EBS volume type: gp2 | gp3 (null for EC2)
    storage_size_gb  - EBS volume size in GB (float, null for EC2)
    days_unattached  - Days the EBS volume has been unattached (int, null if attached)
"""

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


# ─────────────────────────────────────────────────────────────
# Required columns
# ─────────────────────────────────────────────────────────────

REQUIRED_COLUMNS: list[str] = ["resource_id", "resource_type", "monthly_cost"]

NUMERIC_COLUMNS: list[str] = [
    "monthly_cost",
    "cpu_utilization",
    "storage_size_gb",
    "days_unattached",
]


# ─────────────────────────────────────────────────────────────
# Result
# ─────────────────────────────────────────────────────────────

@dataclass
class ParseResult:
    df: pd.DataFrame
    row_count: int
    skipped_rows: int


# ─────────────────────────────────────────────────────────────
# Parser
# ─────────────────────────────────────────────────────────────

def parse_usage_report(path: Path) -> ParseResult:
    """
    Load and validate the AWS usage report CSV.

    Args:
        path: Path to the usage report CSV file.

    Returns:
        ParseResult with the cleaned DataFrame.
    """
    path = Path(path)

    if not path.exists():
        raise FileNotFoundError(f"[USAGE-PARSER] Report not found: {path}")

    df = pd.read_csv(path, dtype=str, na_values=["", "NULL", "null", "None"])
    df.columns = [col.strip() for col in df.columns]

    initial_count = len(df)

    # Verify required columns
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"[USAGE-PARSER] Missing required columns: {missing}")

    # Normalize resource_type
    df["resource_type"] = df["resource_type"].str.strip().str.upper()

    # Cast numeric columns
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # Drop rows with missing critical fields
    df = df.dropna(subset=["resource_id", "monthly_cost"])
    df["resource_id"] = df["resource_id"].str.strip()
    skipped = initial_count - len(df)
    df = df.reset_index(drop=True)

    print(f"[USAGE-PARSER] Loaded {path.name}: {len(df)} rows ({skipped} skipped)")
    return ParseResult(df=df, row_count=len(df), skipped_rows=skipped)
