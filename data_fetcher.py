"""
data_fetcher.py - Market Data Fetcher for WhiteLight Simulator
Downloads NDX, TQQQ, SQQQ, QQQ data from Yahoo Finance.
Handles retries, caching, and error recovery.
"""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetches and caches market data from Yahoo Finance."""

    CACHE_DIR = Path("outputs/cache")
    MAX_RETRIES = 3
    RETRY_DELAY = 5  # seconds

    def __init__(self, config: dict):
        self.tickers = config["tickers"]
        self.lookback = config["simulation"]["lookback_days"]
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def fetch_all(self) -> Dict[str, pd.DataFrame]:
        """
        Fetch OHLCV data for all configured tickers.
        Returns dict of {ticker_key: DataFrame}.
        """
        data = {}
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.lookback + 30)  # buffer

        for key, ticker in self.tickers.items():
            logger.info(f"Fetching {ticker} ({key})...")
            df = self._fetch_single(ticker, start_date, end_date)
            if df is not None and not df.empty:
                data[key] = df
                logger.info(f"  -> {len(df)} rows, {df.index[0].date()} to {df.index[-1].date()}")
            else:
                logger.error(f"  -> FAILED to fetch {ticker}")
                # Try loading from cache
                cached = self._load_cache(ticker)
                if cached is not None:
                    data[key] = cached
                    logger.warning(f"  -> Using cached data ({len(cached)} rows)")
                else:
                    raise RuntimeError(f"Cannot fetch or load cached data for {ticker}")

        return data

    def _fetch_single(
        self, ticker: str, start: datetime, end: datetime
    ) -> Optional[pd.DataFrame]:
        """Fetch data for a single ticker with retries."""
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                df = yf.download(
                    ticker,
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=True,
                    progress=False,
                )
                if df is not None and not df.empty:
                    # Flatten multi-level columns if present
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    # Ensure standard column names
                    df.columns = [c.title() if isinstance(c, str) else c for c in df.columns]
                    # Cache it
                    self._save_cache(ticker, df)
                    return df
            except Exception as e:
                logger.warning(f"  Attempt {attempt}/{self.MAX_RETRIES} failed for {ticker}: {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(self.RETRY_DELAY * attempt)

        return None

    def _save_cache(self, ticker: str, df: pd.DataFrame) -> None:
        """Save data to local CSV cache."""
        safe_name = ticker.replace("^", "").replace("/", "_")
        path = self.CACHE_DIR / f"{safe_name}_cache.csv"
        df.to_csv(path)

    def _load_cache(self, ticker: str) -> Optional[pd.DataFrame]:
        """Load data from local CSV cache."""
        safe_name = ticker.replace("^", "").replace("/", "_")
        path = self.CACHE_DIR / f"{safe_name}_cache.csv"
        if path.exists():
            df = pd.read_csv(path, index_col=0, parse_dates=True)
            return df
        return None
