from pathlib import Path

import numpy as np
import pandas as pd

try:
    import wrds
except ImportError:
    wrds = None


DATA_DIR = Path(__file__).resolve().parents[1] / "data"

COMMON_SHARE_CODES = (10, 11)
MAJOR_EXCHANGES = (1, 2, 3)


def connect():
    return wrds.Connection(wrds_username="rkolanu")


def get_crsp_daily(db, start, end):
    query = f"""
        SELECT a.permno, a.date, a.ret, a.prc, a.shrout, a.vol
        FROM crsp.dsf AS a
        INNER JOIN crsp.dsenames AS b
            ON a.permno = b.permno
            AND a.date BETWEEN b.namedt AND b.nameendt
        WHERE b.shrcd IN {COMMON_SHARE_CODES}
            AND b.exchcd IN {MAJOR_EXCHANGES}
            AND a.date BETWEEN '{start}' AND '{end}'
    """
    df = db.raw_sql(query, date_cols=["date"])
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    df["mktcap"] = df["prc"].abs() * df["shrout"]
    return (
        df.dropna(subset=["ret"])
        .sort_values(["permno", "date"])
        .reset_index(drop=True)
    )


def get_crsp_monthly(db, start, end):
    msf = db.raw_sql(
        f"""
        SELECT a.permno, a.date, a.ret, a.prc, a.shrout
        FROM crsp.msf AS a
        INNER JOIN crsp.msenames AS b
            ON a.permno = b.permno
            AND a.date BETWEEN b.namedt AND b.nameendt
        WHERE b.shrcd IN {COMMON_SHARE_CODES}
            AND b.exchcd IN {MAJOR_EXCHANGES}
            AND a.date BETWEEN '{start}' AND '{end}'
        """,
        date_cols=["date"],
    )

    dl = db.raw_sql(
        f"""
        SELECT permno, dlret, dlstdt
        FROM crsp.msedelist
        WHERE dlstdt BETWEEN '{start}' AND '{end}'
        """,
        date_cols=["dlstdt"],
    )

    msf["ym"] = msf["date"].dt.to_period("M")
    dl["ym"] = dl["dlstdt"].dt.to_period("M")
    merged = msf.merge(dl[["permno", "ym", "dlret"]], on=["permno", "ym"], how="left")

    r = pd.to_numeric(merged["ret"], errors="coerce")
    d = pd.to_numeric(merged["dlret"], errors="coerce")
    merged["ret_adj"] = (1 + r.fillna(0)) * (1 + d.fillna(0)) - 1
    merged.loc[r.isna() & d.isna(), "ret_adj"] = np.nan

    merged["mktcap"] = merged["prc"].abs() * merged["shrout"]
    out = (
        merged[["permno", "date", "ret_adj", "mktcap"]]
        .rename(columns={"ret_adj": "ret"})
        .dropna(subset=["ret"])
        .sort_values(["permno", "date"])
        .reset_index(drop=True)
    )
    return out


def get_ff_factors(db, start, end, freq="daily"):
    table = "ff.factors_daily" if freq == "daily" else "ff.factors_monthly"
    df = db.raw_sql(
        f"""
        SELECT date, mktrf, smb, hml, umd, rf
        FROM {table}
        WHERE date BETWEEN '{start}' AND '{end}'
        """,
        date_cols=["date"],
    )
    return df.sort_values("date").reset_index(drop=True)


def build_dataset(start="1990-01-01", end="2024-12-31", data_dir=DATA_DIR, refresh=False):
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "daily": data_dir / "crsp_daily.parquet",
        "monthly": data_dir / "crsp_monthly.parquet",
        "ff_daily": data_dir / "ff_daily.parquet",
        "ff_monthly": data_dir / "ff_monthly.parquet",
    }

    if not refresh and all(p.exists() for p in paths.values()):
        return {k: pd.read_parquet(v) for k, v in paths.items()}

    db = connect()
    try:
        data = {
            "daily": get_crsp_daily(db, start, end),
            "monthly": get_crsp_monthly(db, start, end),
            "ff_daily": get_ff_factors(db, start, end, "daily"),
            "ff_monthly": get_ff_factors(db, start, end, "monthly"),
        }
    finally:
        db.close()

    for key, df in data.items():
        df.to_parquet(paths[key], index=False)
    return data


if __name__ == "__main__":
    frames = build_dataset()
    for name, df in frames.items():
        print(f"{name:10s} {len(df):>12,} rows   {df['date'].min()} → {df['date'].max()}")