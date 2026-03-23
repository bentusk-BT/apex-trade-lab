"""
indicators.py - Technical Indicator Calculator for WhiteLight Simulator
Computes SMA(20), SMA(250), Bollinger Bands, RSI, ATR, and extension metrics.
All indicators use NDX (Nasdaq-100 Index) as the signal source.
"""

import logging
from typing import Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def compute_all_indicators(ndx: pd.DataFrame, config: dict) -> pd.DataFrame:
    """
    Compute all technical indicators on NDX data.
    Returns a DataFrame with all indicator columns added.

    Indicators (based on Mallik's public descriptions):
    - SMA(20): Short-term trend
    - SMA(250): Long-term trend / regime filter
    - Bollinger Bands (20, 2): Momentum & overextension detection
    - RSI(14): Supplementary momentum gauge
    - ATR(14): Volatility measurement
    - Extension metrics: How far price is from each MA
    """
    ind = config["indicators"]
    df = ndx.copy()

    # ---- Moving Averages ----
    df["SMA20"] = df["Close"].rolling(window=ind["sma_fast"]).mean()
    df["SMA250"] = df["Close"].rolling(window=ind["sma_slow"]).mean()

    # ---- Extension from MAs (key signal for position sizing) ----
    df["Ext_SMA20_Pct"] = ((df["Close"] - df["SMA20"]) / df["SMA20"]) * 100
    df["Ext_SMA250_Pct"] = ((df["Close"] - df["SMA250"]) / df["SMA250"]) * 100

    # ---- Bollinger Bands ----
    df["BB_Middle"] = df["Close"].rolling(window=ind["bb_period"]).mean()
    bb_std = df["Close"].rolling(window=ind["bb_period"]).std()
    df["BB_Upper"] = df["BB_Middle"] + (ind["bb_std"] * bb_std)
    df["BB_Lower"] = df["BB_Middle"] - (ind["bb_std"] * bb_std)
    df["BB_Width"] = (df["BB_Upper"] - df["BB_Lower"]) / df["BB_Middle"] * 100
    df["BB_Pct"] = (df["Close"] - df["BB_Lower"]) / (df["BB_Upper"] - df["BB_Lower"])

    # ---- RSI ----
    df["RSI"] = _compute_rsi(df["Close"], ind["rsi_period"])

    # ---- ATR ----
    df["ATR"] = _compute_atr(df, ind["atr_period"])

    # ---- Regime Flags ----
    df["Above_SMA250"] = df["Close"] > df["SMA250"]
    df["Above_SMA20"] = df["Close"] > df["SMA20"]
    df["Near_SMA250"] = df["Ext_SMA250_Pct"].abs() <= 5.0  # Within 5%

    # ---- Momentum Flags ----
    df["Above_Upper_BB"] = df["Close"] > df["BB_Upper"]
    df["Below_Lower_BB"] = df["Close"] < df["BB_Lower"]
    df["Above_Middle_BB"] = df["Close"] > df["BB_Middle"]

    # ---- Previous day flags (for crossover detection) ----
    df["Prev_Above_SMA20"] = df["Above_SMA20"].shift(1)
    df["Prev_Above_Upper_BB"] = df["Above_Upper_BB"].shift(1)
    df["Prev_Below_Lower_BB"] = df["Below_Lower_BB"].shift(1)

    # ---- Consecutive days above/below SMA20 ----
    df["Days_Above_SMA20"] = _consecutive_count(df["Above_SMA20"])
    df["Days_Below_SMA20"] = _consecutive_count(~df["Above_SMA20"])

    # ---- Bullish/Bearish reversal candle ----
    df["Bullish_Candle"] = df["Close"] > df["Open"]
    df["Bearish_Candle"] = df["Close"] < df["Open"]

    logger.info(f"Indicators computed: {len(df)} rows, {df.dropna().shape[0]} valid")
    return df


def _compute_rsi(series: pd.Series, period: int) -> pd.Series:
    """Compute Relative Strength Index."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Use Wilder's smoothing after initial SMA
    for i in range(period, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i - 1] * (period - 1) + gain.iloc[i]) / period
        avg_loss.iloc[i] = (avg_loss.iloc[i - 1] * (period - 1) + loss.iloc[i]) / period

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def _compute_atr(df: pd.DataFrame, period: int) -> pd.Series:
    """Compute Average True Range."""
    high = df["High"]
    low = df["Low"]
    close = df["Close"].shift(1)

    tr1 = high - low
    tr2 = (high - close).abs()
    tr3 = (low - close).abs()

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=period).mean()
    return atr


def _consecutive_count(condition: pd.Series) -> pd.Series:
    """Count consecutive True values in a boolean series."""
    groups = (~condition).cumsum()
    result = condition.groupby(groups).cumsum()
    return result
