from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from .schema_mapper import TableSchema, infer_schema, normalize_text


@dataclass
class SheetTable:
    name: str
    dataframe: pd.DataFrame
    header_row: int = 0
    schema: Optional[TableSchema] = None
    source: str = ""

    @property
    def rows(self) -> int:
        return len(self.dataframe)

    @property
    def columns(self) -> List[str]:
        return [str(c) for c in self.dataframe.columns]

    def preview_records(self, limit: int = 5) -> List[Dict[str, Any]]:
        return self.dataframe.head(limit).where(pd.notna(self.dataframe), None).to_dict(orient="records")


@dataclass
class WorkbookData:
    path: str
    filename: str
    tables: List[SheetTable] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def schema_summary(self) -> List[Dict[str, Any]]:
        out = []
        for table in self.tables:
            schema = table.schema
            out.append({
                "sheet": table.name,
                "rows": table.rows,
                "columns": table.columns,
                "roles": schema.as_simple_dict() if schema else {},
                "score": schema.score if schema else 0,
                "warnings": schema.warnings if schema else [],
            })
        return out

    def compact_profile(self, max_rows_per_sheet: int = 4) -> str:
        profile = []
        for table in self.tables:
            profile.append({
                "sheet": table.name,
                "rows": table.rows,
                "columns": table.columns,
                "inferred_roles": table.schema.as_simple_dict() if table.schema else {},
                "sample_rows": table.preview_records(max_rows_per_sheet),
            })
        return json.dumps(profile, default=str, ensure_ascii=False, indent=2)[:12000]


def _clean_columns(columns: List[Any]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for idx, col in enumerate(columns):
        text = str(col).strip() if col is not None else ""
        if not text or text.lower() == "nan" or text.startswith("Unnamed"):
            text = f"Column {idx + 1}"
        text = " ".join(text.split())
        if text in seen:
            seen[text] += 1
            text = f"{text} ({seen[text]})"
        else:
            seen[text] = 1
        result.append(text)
    return result


def _drop_empty(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")
    # Remove fully blank string rows/cols.
    if df.empty:
        return df
    df = df.loc[~df.apply(lambda row: all(str(x).strip() == "" or str(x).lower() == "nan" for x in row), axis=1)]
    if df.empty:
        return df
    df = df.loc[:, ~df.apply(lambda col: all(str(x).strip() == "" or str(x).lower() == "nan" for x in col), axis=0)]
    return df


def _guess_header_row(raw: pd.DataFrame, max_scan_rows: int = 20) -> int:
    if raw.empty:
        return 0
    best_row = 0
    best_score = -1.0
    scan = min(max_scan_rows, len(raw))
    for i in range(scan):
        row = raw.iloc[i]
        non_empty = row.notna().sum()
        if non_empty == 0:
            continue
        values = [str(v).strip() for v in row.tolist() if pd.notna(v) and str(v).strip()]
        unique = len(set(values))
        text_count = sum(any(ch.isalpha() for ch in v) for v in values)
        short_text_count = sum(1 for v in values if any(ch.isalpha() for ch in v) and len(v) <= 60)
        unnamed_penalty = sum(1 for v in values if normalize_text(v).startswith("unnamed"))
        # Header rows usually have several short-ish text labels and high uniqueness.
        score = non_empty * 0.7 + unique * 0.45 + text_count * 1.0 + short_text_count * 0.5 - unnamed_penalty
        # Penalize rows that look like data: many numbers and few strings.
        numericish = 0
        for v in values:
            try:
                float(str(v).replace(",", "."))
                numericish += 1
            except Exception:
                pass
        if numericish > text_count:
            score -= numericish * 0.6
        if score > best_score:
            best_score = score
            best_row = i
    return best_row


def _read_excel_sheet(path: Path, sheet_name: str) -> SheetTable:
    raw = pd.read_excel(path, sheet_name=sheet_name, header=None, dtype=object, engine="openpyxl")
    raw = _drop_empty(raw)
    if raw.empty:
        return SheetTable(name=str(sheet_name), dataframe=pd.DataFrame(), header_row=0, source=str(path))
    header_row = _guess_header_row(raw)
    headers = _clean_columns(raw.iloc[header_row].tolist())
    df = raw.iloc[header_row + 1:].copy()
    df.columns = headers[: len(df.columns)]
    df = _drop_empty(df)
    # If header detection failed and no data remains, read with pandas default.
    if df.empty and len(raw) > 1:
        df = pd.read_excel(path, sheet_name=sheet_name, dtype=object, engine="openpyxl")
        df.columns = _clean_columns(df.columns.tolist())
        df = _drop_empty(df)
    table = SheetTable(name=str(sheet_name), dataframe=df.reset_index(drop=True), header_row=header_row, source=str(path))
    table.schema = infer_schema(table.dataframe, table.name)
    return table


def read_workbook(path: str) -> WorkbookData:
    p = Path(path)
    workbook = WorkbookData(path=str(p), filename=p.name)
    suffix = p.suffix.lower()
    try:
        if suffix in {".xlsx", ".xlsm", ".xltx", ".xltm"}:
            xls = pd.ExcelFile(p, engine="openpyxl")
            for sheet in xls.sheet_names:
                try:
                    table = _read_excel_sheet(p, sheet)
                    if not table.dataframe.empty:
                        workbook.tables.append(table)
                except Exception as exc:
                    workbook.errors.append(f"Could not read sheet '{sheet}': {exc}")
        elif suffix == ".csv":
            df = pd.read_csv(p, dtype=object)
            df.columns = _clean_columns(df.columns.tolist())
            df = _drop_empty(df)
            table = SheetTable(name=p.stem, dataframe=df.reset_index(drop=True), header_row=0, source=str(path))
            table.schema = infer_schema(table.dataframe, table.name)
            workbook.tables.append(table)
        elif suffix == ".xls":
            # Requires xlrd if the user needs legacy xls files.
            xls = pd.ExcelFile(p)
            for sheet in xls.sheet_names:
                try:
                    raw = pd.read_excel(p, sheet_name=sheet, header=None, dtype=object)
                    raw = _drop_empty(raw)
                    if raw.empty:
                        continue
                    header_row = _guess_header_row(raw)
                    headers = _clean_columns(raw.iloc[header_row].tolist())
                    df = raw.iloc[header_row + 1:].copy()
                    df.columns = headers[: len(df.columns)]
                    df = _drop_empty(df)
                    table = SheetTable(name=str(sheet), dataframe=df.reset_index(drop=True), header_row=header_row, source=str(path))
                    table.schema = infer_schema(table.dataframe, table.name)
                    workbook.tables.append(table)
                except Exception as exc:
                    workbook.errors.append(f"Could not read sheet '{sheet}': {exc}")
        else:
            workbook.errors.append(f"Unsupported file type: {suffix}. Use .xlsx, .xlsm, .xls, or .csv.")
    except Exception as exc:
        workbook.errors.append(f"Could not read workbook: {exc}")

    workbook.tables.sort(key=lambda t: t.schema.score if t.schema else 0, reverse=True)
    if not workbook.tables and not workbook.errors:
        workbook.errors.append("No usable tables were found in the workbook.")
    return workbook
