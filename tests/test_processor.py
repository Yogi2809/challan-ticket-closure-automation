import pandas as pd
import pytest
from io import BytesIO


CSV_CONTENT = b"""APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS
APT001,T001,3,3,,,
APT002,T002,3,2,,,
APT003,T003,2,2,1,,
APT004,T004,2,2,,1,
APT005,T005,,,,,
APT006,T006,4,4,,,
"""


def test_load_and_filter_keeps_valid_rows():
    from processor import load_and_filter
    df = load_and_filter(CSV_CONTENT)
    # APT003 has UTF_CHALLANS=1 → excluded
    # APT004 has OPEN_CHALLANS=1 → excluded
    # APT005 has blank CLOSED_CHALLANS → excluded
    assert list(df["APPOINTMENT_ORDER_ID"]) == ["APT001", "APT002", "APT006"]


def test_load_and_filter_normalises_column_names():
    from processor import load_and_filter
    csv = b"  appointment_order_id ,ticket_id,total_challans,closed_challans,utf_challans,open_challans\nAPT001,T001,3,3,,,\n"
    df = load_and_filter(csv)
    assert "APPOINTMENT_ORDER_ID" in df.columns
    assert "TICKET_ID" in df.columns


def test_load_and_filter_returns_empty_if_all_excluded():
    from processor import load_and_filter
    csv = b"APPOINTMENT_ORDER_ID,TICKET_ID,TOTAL_CHALLANS,CLOSED_CHALLANS,UTF_CHALLANS,OPEN_CHALLANS\nAPT001,T001,2,2,1,,\n"
    df = load_and_filter(csv)
    assert df.empty


def test_apply_results_adds_column():
    from processor import apply_results
    df = pd.DataFrame({"APPOINTMENT_ORDER_ID": ["APT001", "APT002"], "TICKET_ID": ["T001", "T002"]})
    results = {"APT001": "SOLVED", "APT002": "MISMATCH"}
    out = apply_results(df, results)
    assert list(out["UPDATED_RESULT"]) == ["SOLVED", "MISMATCH"]


def test_apply_results_does_not_mutate_input():
    from processor import apply_results
    df = pd.DataFrame({"APPOINTMENT_ORDER_ID": ["APT001"], "TICKET_ID": ["T001"]})
    apply_results(df, {"APT001": "SOLVED"})
    assert "UPDATED_RESULT" not in df.columns


def test_build_report_counts_correctly():
    from processor import build_report
    df = pd.DataFrame({
        "APPOINTMENT_ORDER_ID": ["APT001", "APT002", "APT003", "APT004"],
        "TICKET_ID": ["T001", "T002", "T003", "T004"],
        "TOTAL_CHALLANS": [3, 3, 2, 4],
        "CLOSED_CHALLANS": [3, 2, 2, 4],
        "UPDATED_RESULT": ["SOLVED", "MISMATCH", "ERROR", "SOLVED"],
    })
    report = build_report(df)
    assert report["total"] == 4
    assert report["solved"] == 2
    assert report["mismatch"] == 1
    assert report["error"] == 1
    assert len(report["mismatch_rows"]) == 2


def test_build_report_mismatch_rows_contain_required_fields():
    from processor import build_report
    df = pd.DataFrame({
        "APPOINTMENT_ORDER_ID": ["APT002"],
        "TICKET_ID": ["T002"],
        "TOTAL_CHALLANS": [3],
        "CLOSED_CHALLANS": [2],
        "UPDATED_RESULT": ["MISMATCH"],
    })
    report = build_report(df)
    row = report["mismatch_rows"][0]
    assert "APPOINTMENT_ORDER_ID" in row
    assert "TICKET_ID" in row
    assert "TOTAL_CHALLANS" in row
    assert "CLOSED_CHALLANS" in row
    assert "UPDATED_RESULT" in row
