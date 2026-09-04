from dataclasses import dataclass
from pathlib import Path
import pandas as pd


REQUIRED_COLUMNS = ["resource_id", "resource_type", "monthly_cost"]
NUMERIC_COLUMNS = [
    "monthly_cost",
    "cpu_utilization",
    "storage_size_gb",
    "days_unattached",
]


@dataclass
class ParseResult:
    df: pd.DataFrame
    row_count: int
    skipped_rows: int


def parse_usage_report(path: Path) -> ParseResult:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {path}")

    df = pd.read_csv(path, dtype=str, na_values=["", "NULL", "null", "None"])
    df.columns = [col.strip() for col in df.columns]

    initial_count = len(df)

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    df["resource_type"] = df["resource_type"].str.strip().str.upper()

    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df = df.dropna(subset=["resource_id", "monthly_cost"])
    df["resource_id"] = df["resource_id"].str.strip()
    skipped = initial_count - len(df)
    df = df.reset_index(drop=True)

    return ParseResult(df=df, row_count=len(df), skipped_rows=skipped)
