from pathlib import Path

import numpy as np
import pandas as pd

VOL_WINDOW = 252
VOL_MIN = 120
CORR_WINDOW = 1250
CORR_MIN = 750
SHRINK_W = 0.6
SHRINK_TARGET = 1.0


def to_log_returns(wide):
    return np.log1p(wide)


def rolling_vol(log_ret, window=VOL_WINDOW, min_periods=VOL_MIN):
    return log_ret.rolling(window=window, min_periods=min_periods).std()


def three_day_log_returns(log_ret):
    return log_ret.rolling(window=3, min_periods=3).sum()


def rolling_corr(stock_3d, market_3d, window=CORR_WINDOW, min_periods=CORR_MIN):
    return stock_3d.rolling(window=window, min_periods=min_periods).corr(market_3d)


def raw_beta(corr, vol_stock, vol_market):
    return corr.multiply(vol_stock).divide(vol_market, axis=0)


def shrink(beta_raw, w=SHRINK_W, target=SHRINK_TARGET):
    return w * beta_raw + (1 - w) * target


def estimate_betas(daily, market):
    wide = daily.pivot(index="date", columns="permno", values="ret").sort_index()
    market = market.sort_index().reindex(wide.index)

    stock_log = to_log_returns(wide)
    market_log = np.log1p(market)

    vol_stock = rolling_vol(stock_log)
    vol_market = rolling_vol(market_log.to_frame("m"))["m"]

    stock_3d = three_day_log_returns(stock_log)
    market_3d = three_day_log_returns(market_log)

    corr = rolling_corr(stock_3d, market_3d)

    beta_raw = raw_beta(corr, vol_stock, vol_market)
    beta = shrink(beta_raw)

    return beta


def betas_long(daily, market):
    beta = estimate_betas(daily, market)
    out = (
        beta.stack()
        .rename("beta")
        .reset_index()
        .rename(columns={"level_1": "permno"})
        .sort_values(["date", "permno"])
        .reset_index(drop=True)
    )
    return out