"""
simulator.py - WhiteLight Paper Trading Simulator Engine (Enhanced)

Maintains a virtual portfolio, processes strategy signals,
executes paper trades with slippage, and tracks equity curve.

Enhanced logging:
- Each trade includes strategy name + reason text
- Entry vs Exit vs Rebalance labeling
- Market regime at time of trade
- Per-strategy P&L tracking
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from strategies import AggregatedSignal, StrategySignal, Direction

logger = logging.getLogger(__name__)


class Portfolio:
    def __init__(self, starting_capital: float):
        self.starting_capital = starting_capital
        self.cash = starting_capital
        self.positions: Dict[str, Position] = {}
        self.equity_history: List[dict] = []
        self.trade_log: List[dict] = []
        self.signal_log: List[dict] = []
        self.regime_history: List[dict] = []

    @property
    def total_equity(self) -> float:
        return self.cash + sum(p.market_value for p in self.positions.values())

    def get_position_value(self, ticker: str) -> float:
        return self.positions[ticker].market_value if ticker in self.positions else 0.0


class Position:
    def __init__(self, ticker: str, shares: float, avg_price: float, entry_date: str = ""):
        self.ticker = ticker
        self.shares = shares
        self.avg_price = avg_price
        self.current_price = avg_price
        self.entry_date = entry_date

    @property
    def market_value(self) -> float:
        return self.shares * self.current_price


class Simulator:
    def __init__(self, config: dict):
        sim_cfg = config["simulation"]
        self.starting_capital = sim_cfg["starting_capital"]
        self.slippage_bps = sim_cfg["slippage_bps"]
        self.commission = sim_cfg.get("commission_per_trade", 0.0)
        self.min_trade_pct = sim_cfg.get("min_trade_pct", 0.05)
        self.tickers = config["tickers"]
        self.portfolio = Portfolio(self.starting_capital)
        self.state_file = Path(config["outputs"]["csv_dir"]) / config["outputs"]["state_file"]
        self._prev_signal: Optional[AggregatedSignal] = None

    def load_state(self) -> bool:
        if self.state_file.exists():
            try:
                with open(self.state_file, "r") as f:
                    state = json.load(f)
                self.portfolio.cash = state["cash"]
                self.portfolio.positions = {}
                for ticker, pd_ in state.get("positions", {}).items():
                    self.portfolio.positions[ticker] = Position(
                        ticker, pd_["shares"], pd_["avg_price"], pd_.get("entry_date", ""))
                    self.portfolio.positions[ticker].current_price = pd_.get("current_price", pd_["avg_price"])
                self.portfolio.equity_history = state.get("equity_history", [])
                self.portfolio.trade_log = state.get("trade_log", [])
                self.portfolio.signal_log = state.get("signal_log", [])
                self.portfolio.regime_history = state.get("regime_history", [])
                logger.info(f"Loaded state: equity=${self.portfolio.total_equity:,.2f}")
                return True
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
        return False

    def save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "last_updated": datetime.now().isoformat(),
            "cash": self.portfolio.cash,
            "starting_capital": self.starting_capital,
            "total_equity": self.portfolio.total_equity,
            "positions": {
                t: {"shares": p.shares, "avg_price": p.avg_price,
                     "current_price": p.current_price, "entry_date": p.entry_date}
                for t, p in self.portfolio.positions.items()
            },
            "equity_history": self.portfolio.equity_history[-500:],
            "trade_log": self.portfolio.trade_log[-500:],
            "signal_log": self.portfolio.signal_log[-200:],
            "regime_history": self.portfolio.regime_history[-500:],
        }
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2, default=str)

    def run_backfill(self, signals: List[AggregatedSignal], market_data: Dict[str, pd.DataFrame]) -> None:
        tqqq_data, sqqq_data = market_data["long_etf"], market_data["short_etf"]
        for signal in signals:
            date = signal.date
            tp = self._get_next_open(tqqq_data, date)
            sp = self._get_next_open(sqqq_data, date)
            if tp is None or sp is None:
                continue
            self._update_prices(tqqq_data, sqqq_data, date)
            self._rebalance(signal, tp, sp, date)
            self._record_equity(date, signal)
            self._record_regime(date, signal)
            self._prev_signal = signal

    def run_daily(self, signal: AggregatedSignal, market_data: Dict[str, pd.DataFrame]) -> None:
        date = signal.date
        tqqq_data, sqqq_data = market_data["long_etf"], market_data["short_etf"]
        tp = self._get_price_on_date(tqqq_data, date, "Open") or self._get_price_on_date(tqqq_data, date, "Close")
        sp = self._get_price_on_date(sqqq_data, date, "Open") or self._get_price_on_date(sqqq_data, date, "Close")
        if tp is None or sp is None:
            return
        self._update_prices(tqqq_data, sqqq_data, date)
        self._rebalance(signal, tp, sp, date)
        self._record_equity(date, signal)
        self._record_regime(date, signal)
        self._prev_signal = signal

    def _get_regime_label(self, signal: AggregatedSignal) -> str:
        ext = signal.ext_sma250
        if ext > 5: return "STRONG UPTREND"
        elif ext > 0: return "UPTREND"
        elif ext > -5: return "DOWNTREND"
        else: return "STRONG DOWNTREND"

    def _trade_type(self, ticker: str, target_v: float, current_v: float) -> str:
        has = current_v > 10
        wants = target_v > 10
        if not has and wants: return "NEW ENTRY"
        elif has and not wants: return "EXIT"
        elif has and wants:
            if target_v > current_v * 1.1: return "ADD"
            elif target_v < current_v * 0.9: return "REDUCE"
            else: return "REBALANCE"
        return "NONE"

    def _get_strategies_for(self, signal: AggregatedSignal, ticker: str) -> str:
        parts = []
        for s in signal.signals:
            if s.instrument == ticker and s.is_active:
                parts.append(s.name)
            elif s.instrument == ticker and s.exit_triggered:
                parts.append(f"{s.name} (EXIT)")
        return " + ".join(parts) or "Aggregated"

    def _get_reasoning_for(self, signal: AggregatedSignal, ticker: str) -> str:
        parts = [s.reason for s in signal.signals if s.instrument == ticker and (s.is_active or s.exit_triggered)]
        return " | ".join(parts) or "Position rebalance"

    def _rebalance(self, signal, tp, sp, date):
        equity = self.portfolio.total_equity
        tt, st = self.tickers["long_etf"], self.tickers["short_etf"]
        tv_t, tv_s = equity * signal.tqqq_weight, equity * signal.sqqq_weight
        cv_t = self.portfolio.get_position_value(tt)
        cv_s = self.portfolio.get_position_value(st)

        if abs(tv_t - cv_t) / max(equity, 1) > self.min_trade_pct:
            self._execute(tt, tv_t, cv_t, tp, date, signal)
        if abs(tv_s - cv_s) / max(equity, 1) > self.min_trade_pct:
            self._execute(st, tv_s, cv_s, sp, date, signal)

    def _execute(self, ticker, target_v, current_v, price, date, signal):
        if price <= 0:
            return
        pos = self.portfolio.positions.get(ticker)
        cur_shares = pos.shares if pos else 0.0
        exec_price = price * (1 + self.slippage_bps / 10000) if target_v > current_v else price * (1 - self.slippage_bps / 10000)
        target_shares = target_v / exec_price if exec_price > 0 else 0.0
        trade_shares = target_shares - cur_shares
        if abs(trade_shares) < 0.01:
            return

        date_str = str(date.date()) if hasattr(date, 'date') else str(date)
        trade_val = abs(trade_shares * exec_price)
        action = "BUY" if trade_shares > 0 else "SELL"
        tt = self._trade_type(ticker, target_v, current_v)
        realized_pnl = 0.0
        hold_days = 0

        if target_shares <= 0.01:
            if pos:
                realized_pnl = cur_shares * (exec_price - pos.avg_price)
                self.portfolio.cash += cur_shares * exec_price
                if pos.entry_date:
                    try: hold_days = (pd.Timestamp(date_str) - pd.Timestamp(pos.entry_date)).days
                    except: pass
                del self.portfolio.positions[ticker]
        elif trade_shares > 0:
            cost = trade_shares * exec_price + self.commission
            if cost > self.portfolio.cash:
                trade_shares = (self.portfolio.cash - self.commission) / exec_price
                cost = trade_shares * exec_price + self.commission
            self.portfolio.cash -= cost
            if ticker in self.portfolio.positions:
                old = self.portfolio.positions[ticker]
                ts = old.shares + trade_shares
                ap = (old.shares * old.avg_price + trade_shares * exec_price) / ts
                self.portfolio.positions[ticker] = Position(ticker, ts, ap, old.entry_date)
            else:
                self.portfolio.positions[ticker] = Position(ticker, trade_shares, exec_price, date_str)
            self.portfolio.positions[ticker].current_price = exec_price
        else:
            sell_s = abs(trade_shares)
            self.portfolio.cash += sell_s * exec_price - self.commission
            realized_pnl = sell_s * (exec_price - pos.avg_price)
            rem = cur_shares - sell_s
            if rem > 0.01:
                self.portfolio.positions[ticker] = Position(ticker, rem, pos.avg_price, pos.entry_date)
                self.portfolio.positions[ticker].current_price = exec_price
            else:
                if pos.entry_date:
                    try: hold_days = (pd.Timestamp(date_str) - pd.Timestamp(pos.entry_date)).days
                    except: pass
                if ticker in self.portfolio.positions:
                    del self.portfolio.positions[ticker]

        eq_after = self.portfolio.total_equity
        alloc = self.portfolio.get_position_value(ticker) / eq_after * 100 if eq_after > 0 else 0

        self.portfolio.trade_log.append({
            "date": date_str,
            "ticker": ticker,
            "action": action,
            "trade_type": tt,
            "shares": round(abs(trade_shares), 4),
            "price": round(exec_price, 2),
            "value": round(trade_val, 2),
            "realized_pnl": round(realized_pnl, 2),
            "equity_after": round(eq_after, 2),
            "allocation_after_pct": round(alloc, 1),
            "hold_days": hold_days,
            "strategy": self._get_strategies_for(signal, ticker),
            "reasoning": self._get_reasoning_for(signal, ticker),
            "regime": self._get_regime_label(signal),
            "ndx_close": round(signal.ndx_close, 2),
            "ndx_vs_sma20": f"{signal.ext_sma20:+.1f}%",
            "ndx_vs_sma250": f"{signal.ext_sma250:+.1f}%",
            "rsi": round(signal.rsi, 1),
            "execution_timing": "D+1 open (decision 10min before close)",
        })

    def _record_equity(self, date, signal):
        tt, st = self.tickers["long_etf"], self.tickers["short_etf"]
        date_str = str(date.date()) if hasattr(date, 'date') else str(date)
        details = "; ".join(f"{s.name}: {s.reason}" for s in signal.signals if s.is_active)
        rec = {
            "date": date_str,
            "equity": round(self.portfolio.total_equity, 2),
            "cash": round(self.portfolio.cash, 2),
            "tqqq_value": round(self.portfolio.get_position_value(tt), 2),
            "sqqq_value": round(self.portfolio.get_position_value(st), 2),
            "tqqq_alloc": round(signal.tqqq_weight * 100, 1),
            "sqqq_alloc": round(signal.sqqq_weight * 100, 1),
            "cash_alloc": round(signal.cash_weight * 100, 1),
            "ndx_close": round(signal.ndx_close, 2),
            "sma20": round(signal.sma20, 2) if not np.isnan(signal.sma20) else None,
            "sma250": round(signal.sma250, 2) if not np.isnan(signal.sma250) else None,
            "ext_sma20": round(signal.ext_sma20, 2),
            "ext_sma250": round(signal.ext_sma250, 2),
            "rsi": round(signal.rsi, 1),
            "regime": self._get_regime_label(signal),
            "active_strategies": ", ".join(signal.active_strategies),
            "strategy_details": details,
        }
        self.portfolio.equity_history.append(rec)
        self.portfolio.signal_log.append({
            "date": date_str, "tqqq_weight": signal.tqqq_weight,
            "sqqq_weight": signal.sqqq_weight, "cash_weight": signal.cash_weight,
            "regime": rec["regime"], "ndx_close": rec["ndx_close"],
            "ext_sma20": rec["ext_sma20"], "ext_sma250": rec["ext_sma250"],
            "rsi": rec["rsi"], "active_strategies": rec["active_strategies"],
            "strategy_details": details,
        })

    def _record_regime(self, date, signal):
        regime = self._get_regime_label(signal)
        ds = str(date.date()) if hasattr(date, 'date') else str(date)
        if not self.portfolio.regime_history or self.portfolio.regime_history[-1]["regime"] != regime:
            self.portfolio.regime_history.append({
                "date": ds, "regime": regime,
                "ndx_close": round(signal.ndx_close, 2),
                "ext_sma250": round(signal.ext_sma250, 2),
            })

    def _update_prices(self, tqqq_data, sqqq_data, date):
        for ticker, data in [(self.tickers["long_etf"], tqqq_data), (self.tickers["short_etf"], sqqq_data)]:
            p = self._get_price_on_date(data, date, "Close")
            if p and ticker in self.portfolio.positions:
                self.portfolio.positions[ticker].current_price = p

    def _get_next_open(self, data, date):
        future = data.loc[data.index > date]
        return float(future.iloc[0]["Open"]) if not future.empty else self._get_price_on_date(data, date, "Close")

    def _get_price_on_date(self, data, date, col="Close"):
        if date in data.index: return float(data.loc[date, col])
        prior = data.loc[data.index <= date]
        return float(prior.iloc[-1][col]) if not prior.empty else None

    def get_performance_stats(self) -> dict:
        if not self.portfolio.equity_history:
            return {}
        eq = pd.Series(
            [r["equity"] for r in self.portfolio.equity_history],
            index=pd.to_datetime([r["date"] for r in self.portfolio.equity_history]),
        )
        if len(eq) < 2:
            return {"total_return_pct": 0.0}

        ret = (eq.iloc[-1] / self.starting_capital - 1) * 100
        dr = eq.pct_change().dropna()
        days = (eq.index[-1] - eq.index[0]).days
        years = max(days / 365.25, 0.01)
        cagr = ((eq.iloc[-1] / self.starting_capital) ** (1 / years) - 1) * 100
        dd = ((eq - eq.cummax()) / eq.cummax() * 100).min()
        sharpe = (dr.mean() / dr.std()) * np.sqrt(252) if dr.std() > 0 else 0
        trades = self.portfolio.trade_log
        sells = [t for t in trades if t["action"] == "SELL" and t.get("realized_pnl", 0) != 0]
        wins = len([t for t in sells if t["realized_pnl"] > 0])
        losses = len([t for t in sells if t["realized_pnl"] < 0])

        # Regime stats
        regime_stats = {}
        if self.portfolio.equity_history:
            df = pd.DataFrame(self.portfolio.equity_history)
            df["equity"] = pd.to_numeric(df["equity"])
            df["daily_return"] = df["equity"].pct_change()
            for regime in df["regime"].dropna().unique():
                mask = df["regime"] == regime
                rr = df.loc[mask, "daily_return"].dropna()
                if len(rr) < 2: continue
                rt = [t for t in trades if t.get("regime") == regime]
                regime_stats[regime] = {
                    "days": int(mask.sum()),
                    "avg_daily_pct": round(rr.mean() * 100, 3),
                    "total_return_pct": round(((1 + rr).prod() - 1) * 100, 2),
                    "volatility_ann_pct": round(rr.std() * np.sqrt(252) * 100, 1),
                    "trades": len(rt),
                    "pct_of_time": round(mask.sum() / len(df) * 100, 1),
                }

        return {
            "starting_capital": self.starting_capital,
            "current_equity": round(eq.iloc[-1], 2),
            "total_return_pct": round(ret, 2),
            "cagr_pct": round(cagr, 2),
            "max_drawdown_pct": round(dd, 2),
            "sharpe_ratio": round(sharpe, 2),
            "total_trades": len(trades),
            "trades_per_month": round(len(trades) / max(years, 0.01) / 12, 1),
            "win_rate_pct": round(wins / max(wins + losses, 1) * 100, 1),
            "winning_trades": wins,
            "losing_trades": losses,
            "total_realized_pnl": round(sum(t.get("realized_pnl", 0) for t in trades), 2),
            "simulation_days": days,
            "last_updated": str(eq.index[-1].date()),
            "regime_stats": regime_stats,
        }
