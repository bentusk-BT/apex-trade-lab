"""
strategies.py - WhiteLight 7 Sub-Strategy Signal Generator

Reverse-engineered from Mallik's (@RealTQQQTrader) public descriptions:
  - 1 Momentum Long (TQQQ)
  - 3 Mean Reversion Longs (TQQQ)
  - 1 Mean Reversion Short (SQQQ)
  - 2 Momentum Shorts (SQQQ)

Each strategy outputs a target allocation weight [0.0 to strategy.weight].
The simulator aggregates all active strategy weights to determine
total TQQQ vs SQQQ exposure.

ASSUMPTIONS (where Mallik's exact rules are proprietary):
- Entry/exit thresholds estimated from his described behavior
  ("sells into strength, buys into weakness")
- Position sizing logic estimated from his public equity curve behavior
- All assumptions are documented and conservative
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class Direction(Enum):
    LONG = "long"    # TQQQ
    SHORT = "short"  # SQQQ


@dataclass
class StrategySignal:
    """Output from a single strategy evaluation."""
    name: str
    direction: Direction
    instrument: str           # TQQQ or SQQQ
    target_weight: float      # 0.0 = flat, up to max weight
    is_active: bool           # Whether regime filter passes
    entry_triggered: bool     # New entry signal this bar
    exit_triggered: bool      # Exit signal this bar
    reason: str = ""          # Human-readable explanation


@dataclass
class AggregatedSignal:
    """Combined output from all 7 strategies."""
    date: pd.Timestamp
    tqqq_weight: float        # Total target TQQQ allocation (0 to 1)
    sqqq_weight: float        # Total target SQQQ allocation (0 to 1)
    cash_weight: float        # Remainder in cash
    active_strategies: List[str]
    signals: List[StrategySignal]
    ndx_close: float
    sma20: float
    sma250: float
    ext_sma20: float
    ext_sma250: float
    rsi: float


class WhiteLightStrategies:
    """
    Evaluates all 7 WhiteLight sub-strategies and produces
    an aggregated allocation signal.
    """

    def __init__(self, config: dict):
        self.strategies_config = config["strategies"]
        # Track state for strategies that need memory (e.g., failed bounce)
        self._state: Dict[str, dict] = {}

    def evaluate(self, indicators: pd.DataFrame, bar_idx: int) -> AggregatedSignal:
        """
        Evaluate all strategies for a given bar.

        Args:
            indicators: Full DataFrame with all indicator columns
            bar_idx: Integer index of current bar (row position)

        Returns:
            AggregatedSignal with combined TQQQ/SQQQ weights
        """
        row = indicators.iloc[bar_idx]
        prev = indicators.iloc[bar_idx - 1] if bar_idx > 0 else row

        signals: List[StrategySignal] = []

        # Evaluate each of the 7 strategies
        signals.append(self._momentum_long_1(row, prev))
        signals.append(self._mean_reversion_long_1(row, prev))
        signals.append(self._mean_reversion_long_2(row, prev))
        signals.append(self._mean_reversion_long_3(row, prev))
        signals.append(self._mean_reversion_short_1(row, prev))
        signals.append(self._momentum_short_1(row, prev))
        signals.append(self._momentum_short_2(row, prev, indicators, bar_idx))

        # Aggregate: sum TQQQ weights, sum SQQQ weights
        tqqq_weight = sum(
            s.target_weight for s in signals
            if s.direction == Direction.LONG and s.is_active
        )
        sqqq_weight = sum(
            s.target_weight for s in signals
            if s.direction == Direction.SHORT and s.is_active
        )

        # Cap at 100% each side
        tqqq_weight = min(tqqq_weight, 1.0)
        sqqq_weight = min(sqqq_weight, 1.0)

        # If both long and short signals, net them out
        # (Mallik is either TQQQ or SQQQ, rarely both)
        if tqqq_weight > 0 and sqqq_weight > 0:
            if tqqq_weight >= sqqq_weight:
                tqqq_weight -= sqqq_weight
                sqqq_weight = 0.0
            else:
                sqqq_weight -= tqqq_weight
                tqqq_weight = 0.0

        cash_weight = 1.0 - tqqq_weight - sqqq_weight

        active = [s.name for s in signals if s.is_active and s.target_weight > 0]

        return AggregatedSignal(
            date=row.name if hasattr(row, 'name') else indicators.index[bar_idx],
            tqqq_weight=round(tqqq_weight, 4),
            sqqq_weight=round(sqqq_weight, 4),
            cash_weight=round(max(cash_weight, 0.0), 4),
            active_strategies=active,
            signals=signals,
            ndx_close=row["Close"],
            sma20=row.get("SMA20", np.nan),
            sma250=row.get("SMA250", np.nan),
            ext_sma20=row.get("Ext_SMA20_Pct", 0.0),
            ext_sma250=row.get("Ext_SMA250_Pct", 0.0),
            rsi=row.get("RSI", 50.0),
        )

    # ================================================================
    # STRATEGY 1: Momentum Long (TQQQ)
    # Ride NDX momentum when above SMA250 + breaking upper BB
    # ================================================================
    def _momentum_long_1(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["momentum_long_1"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        regime_ok = bool(row.get("Above_SMA250", False))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if regime_ok:
            # Entry: price above upper BB and above SMA20
            above_upper_bb = bool(row.get("Above_Upper_BB", False))
            above_sma20 = bool(row.get("Above_SMA20", False))

            if above_upper_bb and above_sma20:
                entry = True
                # Scale weight by BB width (wider = stronger momentum)
                bb_width = row.get("BB_Width", 5.0)
                scale = min(bb_width / 8.0, 1.0)  # Normalize: 8% width = full weight
                weight = cfg["weight"] * max(scale, 0.5)
                reason = f"Momentum: NDX above upper BB, BB_width={bb_width:.1f}%"
            elif above_sma20:
                # Still in trend but not breaking out - reduced position
                weight = cfg["weight"] * 0.3
                reason = "Momentum: holding above SMA20, reduced size"
            else:
                exit_ = True
                reason = "Momentum: closed below SMA20"
        else:
            reason = "Regime: NDX below SMA250"

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.LONG,
            instrument="TQQQ",
            target_weight=round(weight, 4),
            is_active=regime_ok and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 2: Mean Reversion Long 1 (TQQQ)
    # Buy pullback to SMA20 in uptrend
    # ================================================================
    def _mean_reversion_long_1(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["mean_reversion_long_1"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        regime_ok = bool(row.get("Above_SMA250", False))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if regime_ok:
            ext = row.get("Ext_SMA20_Pct", 0.0)
            threshold = cfg["entry"]["threshold_pct"]
            exit_threshold = cfg["exit"]["threshold_pct"]

            # Entry: price pulled back to within threshold% of SMA20
            if -threshold <= ext <= threshold:
                entry = True
                # Inverse sizing: more oversold = larger position
                oversold_factor = max(1.0 - (ext / threshold), 0.5) if ext < 0 else 0.6
                weight = cfg["weight"] * oversold_factor
                reason = f"MR Long 1: pullback to SMA20, ext={ext:.1f}%"
            elif ext > exit_threshold:
                exit_ = True
                reason = f"MR Long 1: extended {ext:.1f}% above SMA20, exit"
            elif ext < -5.0:
                reason = f"MR Long 1: too far below SMA20 ({ext:.1f}%), deferring to MR2"
            else:
                reason = f"MR Long 1: ext={ext:.1f}%, no trigger"
        else:
            reason = "Regime: NDX below SMA250"

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.LONG,
            instrument="TQQQ",
            target_weight=round(weight, 4),
            is_active=regime_ok and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 3: Mean Reversion Long 2 (TQQQ)
    # Buy deep pullback below lower BB in uptrend
    # ================================================================
    def _mean_reversion_long_2(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["mean_reversion_long_2"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        regime_ok = bool(row.get("Above_SMA250", False))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if regime_ok:
            below_lower_bb = bool(row.get("Below_Lower_BB", False))
            above_middle_bb = bool(row.get("Above_Middle_BB", False))
            ext = row.get("Ext_SMA20_Pct", 0.0)

            if below_lower_bb:
                entry = True
                # Deeper pullback = larger position (buy the dip aggressively)
                depth_factor = min(abs(ext) / 5.0, 1.0)
                weight = cfg["weight"] * max(depth_factor, 0.6)
                reason = f"MR Long 2: deep pullback below lower BB, ext={ext:.1f}%"
            elif not above_middle_bb and ext < -1.0:
                # Between lower BB and middle BB, still recovering
                weight = cfg["weight"] * 0.4
                reason = f"MR Long 2: recovering below middle BB, ext={ext:.1f}%"
            elif above_middle_bb and self._was_active("mr_long_2"):
                exit_ = True
                reason = "MR Long 2: recovered above middle BB, exit"
            else:
                reason = f"MR Long 2: no trigger, ext={ext:.1f}%"

            self._update_state("mr_long_2", entry or (weight > 0))
        else:
            reason = "Regime: NDX below SMA250"

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.LONG,
            instrument="TQQQ",
            target_weight=round(weight, 4),
            is_active=regime_ok and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 4: Mean Reversion Long 3 (TQQQ)
    # Buy bounce near SMA250 support
    # ================================================================
    def _mean_reversion_long_3(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["mean_reversion_long_3"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        ext_250 = row.get("Ext_SMA250_Pct", 0.0)
        near_sma250 = abs(ext_250) <= 5.0
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if near_sma250:
            threshold = cfg["entry"]["threshold_pct"]
            bullish = bool(row.get("Bullish_Candle", False))

            # Entry: within 3% of SMA250 and bullish reversal candle
            if abs(ext_250) <= threshold and bullish:
                entry = True
                weight = cfg["weight"]
                reason = f"MR Long 3: bounce near SMA250, ext250={ext_250:.1f}%"
            elif abs(ext_250) <= threshold:
                weight = cfg["weight"] * 0.5
                reason = f"MR Long 3: near SMA250 but no reversal candle"
            else:
                reason = f"MR Long 3: near zone but |ext|>{threshold}%"

            # Exit: extended above SMA20 exit threshold
            ext_20 = row.get("Ext_SMA20_Pct", 0.0)
            if ext_20 > cfg["exit"]["threshold_pct"]:
                exit_ = True
                weight = 0.0
                reason = f"MR Long 3: extended above SMA20 ({ext_20:.1f}%), exit"
        else:
            reason = f"Regime: NDX not near SMA250 (ext250={ext_250:.1f}%)"

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.LONG,
            instrument="TQQQ",
            target_weight=round(weight, 4),
            is_active=near_sma250 and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 5: Mean Reversion Short (SQQQ)
    # Short NDX when extremely overextended above SMA20
    # ================================================================
    def _mean_reversion_short_1(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["mean_reversion_short_1"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        regime_ok = bool(row.get("Above_SMA250", False))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if regime_ok:
            ext = row.get("Ext_SMA20_Pct", 0.0)
            threshold = cfg["entry"]["threshold_pct"]
            exit_threshold = cfg["exit"]["threshold_pct"]
            above_upper_bb = bool(row.get("Above_Upper_BB", False))

            # Entry: NDX >4% above SMA20 AND above upper BB
            if ext > threshold and above_upper_bb:
                entry = True
                weight = cfg["weight"]
                reason = f"MR Short: overextended {ext:.1f}% above SMA20 + above upper BB"
            elif ext > threshold:
                weight = cfg["weight"] * 0.5
                reason = f"MR Short: overextended {ext:.1f}% but not above upper BB"
            elif self._was_active("mr_short_1") and ext > exit_threshold:
                # Still holding short, not yet reverted
                weight = cfg["weight"] * 0.5
                reason = f"MR Short: holding, ext={ext:.1f}%"
            elif self._was_active("mr_short_1"):
                exit_ = True
                reason = f"MR Short: reverted to SMA20 (ext={ext:.1f}%), exit"
            else:
                reason = f"MR Short: ext={ext:.1f}%, below threshold"

            self._update_state("mr_short_1", weight > 0)
        else:
            reason = "MR Short: inactive (NDX below SMA250, shorts handled by momentum)"

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.SHORT,
            instrument="SQQQ",
            target_weight=round(weight, 4),
            is_active=regime_ok and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 6: Momentum Short 1 (SQQQ)
    # Short NDX when breaking below SMA250 (trend breakdown)
    # ================================================================
    def _momentum_short_1(self, row: pd.Series, prev: pd.Series) -> StrategySignal:
        cfg = self.strategies_config["momentum_short_1"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        below_sma250 = not bool(row.get("Above_SMA250", True))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if below_sma250:
            below_lower_bb = bool(row.get("Below_Lower_BB", False))
            ext_250 = row.get("Ext_SMA250_Pct", 0.0)

            if below_lower_bb:
                entry = True
                # Scale by extension below SMA250
                depth = min(abs(ext_250) / 10.0, 1.0)
                weight = cfg["weight"] * max(depth, 0.5)
                reason = f"Mom Short 1: breakdown below SMA250 + lower BB, ext250={ext_250:.1f}%"
            elif ext_250 < -2.0:
                # Below SMA250 and falling
                weight = cfg["weight"] * 0.6
                reason = f"Mom Short 1: below SMA250 ({ext_250:.1f}%), maintaining short"
            else:
                weight = cfg["weight"] * 0.3
                reason = f"Mom Short 1: just below SMA250 ({ext_250:.1f}%), light short"
        else:
            if self._was_active("mom_short_1"):
                exit_ = True
                reason = "Mom Short 1: NDX reclaimed SMA250, exit"
            else:
                reason = "Mom Short 1: inactive (NDX above SMA250)"

        self._update_state("mom_short_1", below_sma250 and weight > 0)

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.SHORT,
            instrument="SQQQ",
            target_weight=round(weight, 4),
            is_active=below_sma250 and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ================================================================
    # STRATEGY 7: Momentum Short 2 (SQQQ)
    # Short on failed bounce back below SMA20 in downtrend
    # ================================================================
    def _momentum_short_2(
        self, row: pd.Series, prev: pd.Series,
        indicators: pd.DataFrame, bar_idx: int
    ) -> StrategySignal:
        cfg = self.strategies_config["momentum_short_2"]
        if not cfg.get("enabled", True):
            return self._inactive_signal(cfg)

        below_sma250 = not bool(row.get("Above_SMA250", True))
        entry = False
        exit_ = False
        weight = 0.0
        reason = ""

        if below_sma250:
            above_sma20_now = bool(row.get("Above_SMA20", False))
            was_above_sma20 = bool(prev.get("Prev_Above_SMA20", False)) if prev is not None else False

            # Failed bounce: was above SMA20 yesterday, now below
            if not above_sma20_now and was_above_sma20:
                entry = True
                weight = cfg["weight"]
                reason = "Mom Short 2: failed bounce below SMA20 in downtrend"
            elif not above_sma20_now and self._was_active("mom_short_2"):
                weight = cfg["weight"] * 0.7
                reason = "Mom Short 2: holding, still below SMA20"
            elif above_sma20_now:
                # Check if above SMA20 for sustained_days consecutive days
                days_above = int(row.get("Days_Above_SMA20", 0))
                sustained = cfg["exit"].get("days", 3)
                if days_above >= sustained and self._was_active("mom_short_2"):
                    exit_ = True
                    reason = f"Mom Short 2: above SMA20 for {days_above} days, exit"
                elif self._was_active("mom_short_2"):
                    weight = cfg["weight"] * 0.3
                    reason = f"Mom Short 2: above SMA20 {days_above}/{sustained} days, reducing"
                else:
                    reason = "Mom Short 2: above SMA20, watching for fail"
            else:
                reason = "Mom Short 2: no trigger"

            self._update_state("mom_short_2", weight > 0)
        else:
            if self._was_active("mom_short_2"):
                exit_ = True
                reason = "Mom Short 2: NDX reclaimed SMA250, exit"
            else:
                reason = "Mom Short 2: inactive (NDX above SMA250)"
            self._update_state("mom_short_2", False)

        return StrategySignal(
            name=cfg["name"],
            direction=Direction.SHORT,
            instrument="SQQQ",
            target_weight=round(weight, 4),
            is_active=below_sma250 and weight > 0,
            entry_triggered=entry,
            exit_triggered=exit_,
            reason=reason,
        )

    # ---- Helper methods ----

    def _inactive_signal(self, cfg: dict) -> StrategySignal:
        direction = Direction.LONG if cfg.get("direction") == "long" else Direction.SHORT
        instrument = cfg.get("instrument", "TQQQ")
        return StrategySignal(
            name=cfg["name"],
            direction=direction,
            instrument=instrument,
            target_weight=0.0,
            is_active=False,
            entry_triggered=False,
            exit_triggered=False,
            reason="Strategy disabled",
        )

    def _was_active(self, key: str) -> bool:
        return self._state.get(key, {}).get("active", False)

    def _update_state(self, key: str, active: bool) -> None:
        if key not in self._state:
            self._state[key] = {}
        self._state[key]["active"] = active
