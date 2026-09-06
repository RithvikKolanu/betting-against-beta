from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

ANNUALIZATION = 12
NW_LAGS = 6


def merge_factors(bab, ff_monthly):
    ff = ff_monthly.copy()
    ff["month"] = ff["date"].dt.to_period("M")
    left = bab[["month", "bab"]].copy()
    merged = left.merge(ff, on="month", how="inner").sort_values("month").reset_index(drop=True)
    return merged


def summary_stats(bab_series, ann=ANNUALIZATION):
    r = bab_series.dropna()
    mean_m = r.mean()
    vol_m = r.std(ddof=1)
    sharpe = (mean_m / vol_m) * np.sqrt(ann) if vol_m > 0 else np.nan
    return {
        "n_months": len(r),
        "mean_ann": mean_m * ann,
        "vol_ann": vol_m * np.sqrt(ann),
        "sharpe_ann": sharpe,
        "min": r.min(),
        "max": r.max(),
    }


def run_regression(y, X, nw_lags=NW_LAGS):
    X = sm.add_constant(X)
    model = sm.OLS(y, X, missing="drop")
    res = model.fit(cov_type="HAC", cov_kwds={"maxlags": nw_lags})
    return res


def capm_alpha(merged, nw_lags=NW_LAGS, ann=ANNUALIZATION):
    y = merged["bab"]
    X = merged[["mktrf"]]
    res = run_regression(y, X, nw_lags)
    return _alpha_row(res, "CAPM", ann)


def ff4_alpha(merged, nw_lags=NW_LAGS, ann=ANNUALIZATION):
    y = merged["bab"]
    X = merged[["mktrf", "smb", "hml", "umd"]]
    res = run_regression(y, X, nw_lags)
    return _alpha_row(res, "FF3+UMD", ann)


def _alpha_row(res, label, ann):
    alpha_m = res.params["const"]
    t_alpha = res.tvalues["const"]
    loadings = res.params.drop("const").to_dict()
    return {
        "model": label,
        "alpha_ann": alpha_m * ann,
        "alpha_t": t_alpha,
        "loadings": loadings,
        "r2": res.rsquared,
    }


def evaluate(bab, ff_monthly):
    merged = merge_factors(bab, ff_monthly)

    stats = summary_stats(merged["bab"])
    capm = capm_alpha(merged)
    ff4 = ff4_alpha(merged)

    return {
        "summary": stats,
        "capm": capm,
        "ff4": ff4,
        "merged": merged,
    }