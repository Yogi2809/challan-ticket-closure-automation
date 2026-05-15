import pandas as pd
from io import BytesIO


def load_and_filter(csv_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(BytesIO(csv_bytes), index_col=False)
    df.columns = [col.strip().upper() for col in df.columns]

    def is_blank(series: pd.Series) -> pd.Series:
        return series.isna() | (series.astype(str).str.strip() == "") | (series.astype(str).str.strip() == "nan")

    def is_filled(series: pd.Series) -> pd.Series:
        return ~is_blank(series)

    mask = (
        is_blank(df["UTF_CHALLANS"])
        & is_blank(df["OPEN_CHALLANS"])
        & is_filled(df["APPOINTMENT_ORDER_ID"])
        & is_filled(df["CLOSED_CHALLANS"])
    )

    return df[mask].reset_index(drop=True)


def apply_results(df: pd.DataFrame, results: dict) -> pd.DataFrame:
    df = df.copy()
    df["UPDATED_RESULT"] = df["APPOINTMENT_ORDER_ID"].astype(str).map(results)
    return df


def build_report(df: pd.DataFrame) -> dict:
    total = len(df)
    solved = int((df["UPDATED_RESULT"] == "SOLVED").sum())
    mismatch = int((df["UPDATED_RESULT"] == "MISMATCH").sum())
    error = int((df["UPDATED_RESULT"] == "ERROR").sum())

    mismatch_rows = df[df["UPDATED_RESULT"].isin(["MISMATCH", "ERROR"])][
        ["APPOINTMENT_ORDER_ID", "TICKET_ID", "TOTAL_CHALLANS", "CLOSED_CHALLANS", "UPDATED_RESULT"]
    ].to_dict("records")

    return {
        "total": total,
        "solved": solved,
        "mismatch": mismatch,
        "error": error,
        "mismatch_rows": mismatch_rows,
    }
