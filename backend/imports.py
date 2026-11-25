"""Upload preview and confirmation endpoints for the single-company demo.

Files are parsed into an in-memory preview first.  Nothing is written until
the client explicitly confirms the returned import id.  The persisted CSVs
remain compatible with the existing analytics service.
"""
from __future__ import annotations

import io
import json
import math
import os
import re
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from request_context import session_file, session_id

router = APIRouter(prefix="/api/imports", tags=["imports"])

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data2"
EXPENSE_COLUMNS = ["expense_id", "date", "amount", "description", "vendor", "department", "category"]
BUDGET_COLUMNS = ["department", "category", "month", "budgeted_amount"]
PREVIEWS: dict[str, dict] = {}

ALIASES = {
    "date": {"date", "transaction date", "transaction_date", "posted date", "posted_date"},
    "amount": {"amount", "value", "debit", "transaction amount", "transaction_amount"},
    "description": {"description", "memo", "details", "transaction description", "transaction_description"},
    "vendor": {"vendor", "merchant", "payee", "supplier"},
    "department": {"department", "team", "cost center", "cost_center"},
    "category": {"category", "expense category", "expense_category"},
    "month": {"month", "period", "month/period", "month_period"},
    "budgeted_amount": {"budgeted amount", "budgeted_amount", "budget", "planned amount", "planned_amount"},
}


class ConfirmImport(BaseModel):
    import_id: str


def _normalise(name: object) -> str:
    return re.sub(r"\s+", " ", str(name).strip().lower().replace("_", " "))


def _read_file(contents: bytes, filename: str) -> pd.DataFrame:
    suffix = Path(filename or "").suffix.lower()
    try:
        if suffix == ".csv":
            return pd.read_csv(io.BytesIO(contents), dtype=object)
        if suffix in {".xlsx", ".xls"}:
            return pd.read_excel(io.BytesIO(contents), dtype=object)
    except Exception as exc:
        raise HTTPException(422, f"Could not read this file: {exc}") from exc
    raise HTTPException(415, "Upload a CSV, XLSX, or XLS file.")


def _mapping(columns: list[str], supplied: dict) -> dict[str, str]:
    by_normalised = {_normalise(c): c for c in columns}
    mapped = {field: source for field, source in supplied.items() if source in columns}
    for field, aliases in ALIASES.items():
        if field in mapped:
            continue
        for alias in aliases:
            if alias in by_normalised:
                mapped[field] = by_normalised[alias]
                break
    return mapped


def _month(value: object) -> str | None:
    value = str(value).strip()
    for fmt in ("%Y-%m", "%Y-%m-%d", "%B %Y", "%b %Y"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m")
        except ValueError:
            pass
    return None


def _category(description: str, vendor: str) -> tuple[str, float]:
    text = f"{description} {vendor}".lower()
    rules = [
        ("Cloud Services", ("aws", "amazon web services", "gcp", "google cloud", "azure")),
        ("Software Subscriptions", ("subscription", "github", "slack", "notion", "figma", "zoom", "datadog")),
        ("Marketing & Advertising", ("ads", "advertising", "campaign", "linkedin", "mailchimp", "meta")),
        ("Travel & Transportation", ("flight", "airline", "uber", "lyft", "hotel", "airbnb")),
        ("Salaries & Payroll", ("payroll", "gusto", "salary")),
    ]
    for label, terms in rules:
        if any(term in text for term in terms):
            return label, 0.85
    return "Needs Review", 0.0


def _parse_expenses(frame: pd.DataFrame, mapped: dict[str, str]) -> tuple[list[dict], list[dict]]:
    required = {"date", "amount", "description"}
    missing = required - set(mapped)
    if missing:
        raise HTTPException(422, f"Missing required mapped columns: {', '.join(sorted(missing))}")
    rows, errors = [], []
    for index, row in frame.iterrows():
        try:
            date = pd.to_datetime(row[mapped["date"]], errors="raise").date().isoformat()
            amount = float(str(row[mapped["amount"]]).replace(",", "").replace("$", ""))
            if not math.isfinite(amount) or amount < 0:
                raise ValueError("amount must be a non-negative number")
            description = str(row[mapped["description"]]).strip()
            if not description or pd.isna(row[mapped["description"]]):
                raise ValueError("description is required")
            vendor_value = row.get(mapped.get("vendor"), "")
            department_value = row.get(mapped.get("department"), "Unassigned")
            category_value = row.get(mapped.get("category"), "")
            vendor = "" if pd.isna(vendor_value) else str(vendor_value).strip()
            department = "Unassigned" if pd.isna(department_value) else str(department_value).strip() or "Unassigned"
            category = "" if pd.isna(category_value) else str(category_value).strip()
            if not category or category.lower() == "nan":
                category, confidence = _category(description, vendor)
            else:
                confidence = 1.0
            rows.append({"date": date, "amount": round(amount, 2), "description": description, "vendor": vendor,
                         "department": department, "category": category, "confidence": confidence})
        except Exception as exc:
            errors.append({"row": int(index) + 2, "reason": str(exc)})
    return rows, errors


def _parse_budgets(frame: pd.DataFrame, mapped: dict[str, str]) -> tuple[list[dict], list[dict]]:
    required = {"department", "month", "budgeted_amount"}
    missing = required - set(mapped)
    if missing:
        raise HTTPException(422, f"Missing required mapped columns: {', '.join(sorted(missing))}")
    rows, errors = [], []
    for index, row in frame.iterrows():
        try:
            department = str(row[mapped["department"]]).strip()
            month = _month(row[mapped["month"]])
            amount = float(str(row[mapped["budgeted_amount"]]).replace(",", "").replace("$", ""))
            if not department or department.lower() == "nan" or not month:
                raise ValueError("department and a valid month are required")
            category = str(row.get(mapped.get("category"), "")).strip()
            rows.append({"department": department, "category": "" if category.lower() == "nan" else category,
                         "month": month, "budgeted_amount": round(amount, 2)})
        except Exception as exc:
            errors.append({"row": int(index) + 2, "reason": str(exc)})
    return rows, errors


def _duplicates(kind: str, rows: list[dict]) -> set[int]:
    if kind == "expenses":
        key = lambda r: (r["date"], r["amount"], r["description"], r["vendor"], r["department"])
    else:
        key = lambda r: (r["department"], r["category"], r["month"])
    seen, duplicates = set(), set()
    for i, row in enumerate(rows):
        value = key(row)
        if value in seen:
            duplicates.add(i)
        seen.add(value)
    return duplicates


@router.post("/preview")
async def preview_import(
    kind: str = Form(...), file: UploadFile = File(...), mapping: str | None = Form(None)
):
    if kind not in {"expenses", "budgets"}:
        raise HTTPException(422, "kind must be expenses or budgets")
    try:
        supplied = json.loads(mapping) if mapping else {}
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "mapping must be valid JSON") from exc
    if not isinstance(supplied, dict):
        raise HTTPException(422, "mapping must be a JSON object")
    contents = await file.read(10_000_001)
    if len(contents) > 10_000_000:
        raise HTTPException(413, "This demo accepts files up to 10 MB.")
    frame = _read_file(contents, file.filename or "")
    frame.columns = [str(c).strip() for c in frame.columns]
    mapped = _mapping(frame.columns.tolist(), supplied)
    rows, errors = (_parse_expenses(frame, mapped) if kind == "expenses" else _parse_budgets(frame, mapped))
    if kind == "expenses":
        years = sorted({row["date"][:4] for row in rows})
        if len(years) > 1:
            raise HTTPException(422, "Use one expense file per calendar year. This file contains multiple years.")
        year = years[0] if years else None
        months_covered = sorted({row["date"][:7] for row in rows})
    else:
        year, months_covered = None, []
    duplicates = _duplicates(kind, rows)
    good_rows = [r for i, r in enumerate(rows) if i not in duplicates]
    import_id = str(uuid.uuid4())
    # Retain one pending preview per browser session without replacing another visitor's preview.
    current_session = session_id.get()
    for key, value in list(PREVIEWS.items()):
        if value["session_id"] == current_session:
            PREVIEWS.pop(key)
    PREVIEWS[import_id] = {"kind": kind, "rows": good_rows, "year": year, "session_id": current_session}
    return {"import_id": import_id, "kind": kind, "columns": frame.columns.tolist(), "mapping": mapped,
            "year": year, "months_covered": months_covered,
            "total_rows": len(frame), "valid_rows": len(good_rows), "duplicate_rows": len(duplicates),
            "errors": errors[:50], "preview": good_rows[:10]}


def _atomic_write(frame: pd.DataFrame, path: Path) -> None:
    handle, temporary = tempfile.mkstemp(prefix="finshyt-import-", suffix=".csv", dir=path.parent)
    os.close(handle)
    try:
        frame.to_csv(temporary, index=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@router.post("/confirm")
def confirm_import(payload: ConfirmImport):
    preview = PREVIEWS.get(payload.import_id)
    if not preview or preview["session_id"] != session_id.get():
        raise HTTPException(404, "This import preview has expired or was already confirmed.")
    kind, rows = preview["kind"], preview["rows"]
    if not rows:
        raise HTTPException(422, "No valid rows are available to import.")
    if kind == "expenses":
        path = session_file("expenses.csv") or DATA_DIR / "expenses.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        year = int(preview["year"])
        additions = pd.DataFrame([{**row, "expense_id": f"IMP{year}-{i + 1:06d}"} for i, row in enumerate(rows)])
        additions = additions.reindex(columns=EXPENSE_COLUMNS)
        _atomic_write(additions, path)
        message = f"Imported {len(rows):,} expenses for {year}. This file is now the active ledger."
    else:
        path = session_file("budget.csv") or DATA_DIR / "budget.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_bytes((DATA_DIR / "budget.csv").read_bytes())
        existing = pd.read_csv(path)
        additions = pd.DataFrame(rows).reindex(columns=BUDGET_COLUMNS)
        existing_month = existing.month.map(_month)
        for row in additions.to_dict("records"):
            mask = ((existing.department == row["department"]) & (existing.category.fillna("") == row["category"]) &
                    (existing_month == row["month"]))
            existing = existing.loc[~mask]
        additions["month"] = additions["month"].map(lambda value: datetime.strptime(value, "%Y-%m").strftime("%B %Y"))
        _atomic_write(pd.concat([existing, additions], ignore_index=True), path)
        message = f"Imported {len(rows):,} budgets."
    PREVIEWS.pop(payload.import_id, None)
    return {"imported_rows": len(rows), "kind": kind, "message": message}
