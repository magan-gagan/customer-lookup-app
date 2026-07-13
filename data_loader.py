"""
data_loader.py
Connects to all Google Sheets listed in sheets_config.csv, reads every tab,
auto-detects phone number columns, and builds a searchable index keyed by
normalized phone number.
"""

import re
import csv
import time
import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

CREDENTIALS_FILE = "credentials.json"
SHEETS_CONFIG_FILE = "sheets_config.csv"

# Column header keywords that likely indicate a phone number column
PHONE_HEADER_HINTS = [
    "phone", "mobile", "contact number", "contact no",
    "mobile number", "phone number", "whatsapp", "cell",
]


def normalize_phone(raw):
    """Strip everything except digits, drop a leading country code (91) if
    the result is 12 digits, and return the last 10 digits for matching."""
    if raw is None:
        return None
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 0:
        return None
    if len(digits) > 10:
        digits = digits[-10:]
    if len(digits) != 10:
        return None
    return digits


def looks_like_phone_value(value):
    digits = re.sub(r"\D", "", str(value))
    return 10 <= len(digits) <= 13


def retry_with_backoff(func, *args, max_retries=6, base_delay=5, **kwargs):
    """Call func(*args, **kwargs), retrying with exponential backoff if the
    Google Sheets API returns a 429 (quota exceeded) error."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except gspread.exceptions.APIError as e:
            status = None
            try:
                status = e.response.status_code
            except Exception:
                pass
            if status == 429 and attempt < max_retries - 1:
                wait = base_delay * (2 ** attempt)
                time.sleep(wait)
                continue
            raise


def get_client():
    # When deployed on Streamlit Community Cloud, credentials are stored in
    # st.secrets instead of a local file (since credentials.json can't be
    # safely committed to GitHub). Fall back to the local file for
    # running on your own machine.
    try:
        import streamlit as st
        has_secrets = hasattr(st, "secrets") and len(st.secrets) > 0
    except Exception:
        has_secrets = False

    if has_secrets:
        if "gcp_service_account" not in st.secrets:
            raise RuntimeError(
                "Streamlit secrets are configured but no [gcp_service_account] "
                "section was found. Check Settings -> Secrets on your deployed "
                "app and confirm the section header and all fields are present."
            )
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        return gspread.authorize(creds)

    creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
    return gspread.authorize(creds)


def _clean_cell(value):
    if value is None:
        return ""
    # Strip BOM, non-breaking spaces, and other stray whitespace-like chars
    # that sneak in from copy-pasting URLs out of browsers/Docs/Sheets.
    return value.replace("\ufeff", "").replace("\xa0", " ").strip()


def load_sheet_registry():
    entries = []
    raw_bytes = None
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(SHEETS_CONFIG_FILE, newline="", encoding=enc) as f:
                text = f.read()
            raw_bytes = enc
            break
        except UnicodeDecodeError:
            continue

    if raw_bytes is None:
        raise RuntimeError(
            "Could not read sheets_config.csv with any known encoding. "
            "Try re-saving it as 'CSV UTF-8' from Excel/Google Sheets."
        )

    reader = csv.DictReader(text.splitlines())
    for row in reader:
        url = _clean_cell(row.get("sheet_url", ""))
        name = _clean_cell(row.get("friendly_name", ""))
        if url and "PASTE_SHEET_ID_HERE" not in url:
            entries.append({"friendly_name": name, "sheet_url": url})
    return entries


def detect_phone_columns(header_row):
    """Return list of column names whose header matches known phone hints."""
    matches = []
    for col in header_row:
        col_l = str(col).lower()
        if any(hint in col_l for hint in PHONE_HEADER_HINTS):
            matches.append(col)
    return matches


def build_index(progress_callback=None):
    """
    Returns:
        index: dict mapping normalized_phone -> list of match records
        errors: list of (sheet_name, error_message) for sheets that failed to load
        stats: dict with counts for summary display
    """
    client = get_client()
    registry = load_sheet_registry()

    index = {}
    errors = []
    total_rows = 0
    total_tabs = 0

    for entry in registry:
        name = entry["friendly_name"] or entry["sheet_url"]
        if progress_callback:
            progress_callback(f"Reading: {name}")
        try:
            sh = retry_with_backoff(client.open_by_url, entry["sheet_url"])
        except Exception as e:
            errors.append((name, f"Could not open sheet: {e}"))
            continue

        try:
            worksheet_list = retry_with_backoff(sh.worksheets)
        except Exception as e:
            errors.append((name, f"Could not list tabs: {e}"))
            continue

        for ws in worksheet_list:
            total_tabs += 1
            time.sleep(1.1)  # pace requests to stay under Google's per-minute quota
            try:
                records = retry_with_backoff(ws.get_all_records)
            except Exception as e:
                errors.append((f"{name} / {ws.title}", f"Could not read tab: {e}"))
                continue

            if not records:
                continue

            header_row = list(records[0].keys())
            phone_cols = detect_phone_columns(header_row)

            for row_num, row in enumerate(records, start=2):  # row 1 is header
                total_rows += 1

                # Collect candidate phone values: prefer header-matched columns,
                # fall back to scanning any cell that looks like a phone number.
                candidate_values = []
                if phone_cols:
                    candidate_values = [row.get(c) for c in phone_cols]
                else:
                    candidate_values = [v for v in row.values() if looks_like_phone_value(v)]

                seen_numbers = set()
                for val in candidate_values:
                    norm = normalize_phone(val)
                    if norm and norm not in seen_numbers:
                        seen_numbers.add(norm)
                        index.setdefault(norm, []).append({
                            "sheet_name": name,
                            "tab_name": ws.title,
                            "row_number": row_num,
                            "row_data": row,
                        })

    stats = {
        "sheets_registered": len(registry),
        "tabs_read": total_tabs,
        "rows_scanned": total_rows,
        "unique_phone_numbers": len(index),
    }
    return index, errors, stats
