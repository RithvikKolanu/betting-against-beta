from pathlib import Path

import numpy as np
import pandas as pd

MIN_STOCKS = 20


def monthly_beta_signal(betas_long):
    b = betas_long.dropna(subset=["beta"]).copy()
    b["month"] = b["date"].dt.to_period("M")
    last = (
        b.sort_values("date")
        .groupby(["permno", "month"], as_index=False)
        .last()
    )
    last["signal_month"] = last["month"] + 1
    return last[["permno", "signal_month", "beta"]]


def prepare_monthly_returns(monthly):
    m = monthly.copy()
    m["month"] = m["date"].dt.to_period("M")
    return m[["permno", "month", "ret"]]


def rank_weights(beta):
    z = beta.rank()
    dev = z - z.mean()
    k = 2.0 / dev.abs().sum()
    w_high = k * dev.clip(lower=0)
    w_low = k * (-dev).clip(lower=0)
    return w_low, w_high


def leg_stats(beta, ret, w_low, w_high):
    beta_low = np.dot(w_low, beta)
    beta_high = np.dot(w_high, beta)
    ret_low = np.dot(w_low, ret)
    ret_high = np.dot(w_high, ret)
    return beta_low, beta_high, ret_low, ret_high


def bab_returns(betas_long, monthly, rf, min_stocks=MIN_STOCKS):
    signal = monthly_beta_signal(betas_long)
    rets = prepare_monthly_returns(monthly)

    panel = signal.merge(
        rets,
        left_on=["permno", "signal_month"],
        right_on=["permno", "month"],
        how="inner",
    )

    rf = rf.copy()
    rf["month"] = rf["date"].dt.to_period("M")
    rf = rf[["month", "rf"]]

    records = []
    for month, grp in panel.groupby("signal_month"):
        grp = grp.dropna(subset=["beta", "ret"])
        if len(grp) < min_stocks:
            continue

        w_low, w_high = rank_weights(grp["beta"])
        beta_low, beta_high, ret_low, ret_high = leg_stats(
            grp["beta"].values,
            grp["ret"].values,
            w_low.values,
            w_high.values,
        )

        rf_row = rf.loc[rf["month"] == month, "rf"]
        rf_val = float(rf_row.iloc[0]) if len(rf_row) else 0.0

        bab = (ret_low - rf_val) / beta_low - (ret_high - rf_val) / beta_high

        records.append(
            {
                "month": month,
                "n": len(grp),
                "beta_low": beta_low,
                "beta_high": beta_high,
                "ret_low": ret_low,
                "ret_high": ret_high,
                "bab": bab,
            }
        )

    out = pd.DataFrame.from_records(records).sort_values("month").reset_index(drop=True)
    out["date"] = out["month"].dt.to_timestamp("M")
    return out