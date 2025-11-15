import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)


class SignalStrategy:
    def __init__(self, config: Dict):
        self.config = config
    
    @staticmethod
    def calculate_ema(closes: List[float], period: int) -> List[float]:
        """Calculate EMA manually"""
        if len(closes) < period:
            return []
        
        closes_array = np.array(closes)
        ema_values = []
        
        # Calculate SMA for first value
        sma = np.mean(closes_array[:period])
        ema_values.append(sma)
        
        # Calculate EMA for rest
        multiplier = 2 / (period + 1)
        for price in closes_array[period:]:
            ema = (price - ema_values[-1]) * multiplier + ema_values[-1]
            ema_values.append(ema)
        
        # Pad with initial values
        ema_full = [sma] * period + ema_values[1:]
        return ema_full
    
    @staticmethod
    def calculate_rsi(closes: List[float], period: int = 14) -> float:
        """Calculate RSI (last value)"""
        if len(closes) < period + 1:
            return None
        
        deltas = np.diff(closes)
        seed = deltas[:period+1]
        
        up = seed[seed >= 0].sum() / period
        down = -seed[seed < 0].sum() / period
        
        rs = up / down if down != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        
        for delta in deltas[period+1:]:
            if delta > 0:
                up = (up * (period - 1) + delta) / period
                down = down * (period - 1) / period
            else:
                up = up * (period - 1) / period
                down = (down * (period - 1) - delta) / period
            
            rs = up / down if down != 0 else 0
            rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    @staticmethod
    def calculate_stochastic(highs: List[float], lows: List[float], closes: List[float], 
                           k_period: int = 14, d_period: int = 3) -> Tuple[float, float]:
        """Calculate Stochastic K% and D%"""
        if len(closes) < k_period:
            return None, None
        
        highs_array = np.array(highs[-k_period:])
        lows_array = np.array(lows[-k_period:])
        closes_array = np.array(closes[-k_period:])
        
        highest_high = np.max(highs_array)
        lowest_low = np.min(lows_array)
        
        k = 100 * (closes_array[-1] - lowest_low) / (highest_high - lowest_low) if (highest_high - lowest_low) != 0 else 50
        
        # Calculate D (SMA of K)
        if len(closes) < k_period + d_period:
            d = k
        else:
            # Would need to track K values over time for proper D calculation
            d = k
        
        return k, d
    
    @staticmethod
    def calculate_atr(highs: List[float], lows: List[float], closes: List[float], 
                     period: int = 14) -> float:
        """Calculate ATR"""
        if len(closes) < period:
            return None
        
        tr_values = []
        
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            
            tr = max(high_low, high_close, low_close)
            tr_values.append(tr)
        
        if len(tr_values) < period:
            return None
        
        # Calculate ATR as SMA of TR
        atr = np.mean(tr_values[-period:])
        return atr
    
    def check_bullish_ema(self, ema_fast: List[float], ema_med: List[float], 
                          ema_slow: List[float]) -> bool:
        """Check if EMA trend adalah bullish"""
        if not (ema_fast and ema_med and ema_slow):
            return False
        
        return (ema_fast[-1] > ema_med[-1] > ema_slow[-1])
    
    def check_bearish_ema(self, ema_fast: List[float], ema_med: List[float], 
                          ema_slow: List[float]) -> bool:
        """Check if EMA trend adalah bearish"""
        if not (ema_fast and ema_med and ema_slow):
            return False
        
        return (ema_fast[-1] < ema_med[-1] < ema_slow[-1])
    
    def check_rsi_oversold(self, rsi: float, oversold_level: float = 30) -> bool:
        """Check if RSI oversold"""
        return rsi is not None and rsi < oversold_level
    
    def check_rsi_overbought(self, rsi: float, overbought_level: float = 70) -> bool:
        """Check if RSI overbought"""
        return rsi is not None and rsi > overbought_level
    
    def check_stoch_oversold(self, k: float, d: float, oversold_level: float = 20) -> bool:
        """Check if Stochastic oversold"""
        return k is not None and d is not None and k < oversold_level and d < oversold_level
    
    def check_stoch_overbought(self, k: float, d: float, overbought_level: float = 80) -> bool:
        """Check if Stochastic overbought"""
        return k is not None and d is not None and k > overbought_level and d > overbought_level
    
    def check_stoch_bullish_crossover(self, prev_k: float, prev_d: float, 
                                      curr_k: float, curr_d: float) -> bool:
        """Check if Stochastic K cross above D (bullish)"""
        if not (prev_k and prev_d and curr_k and curr_d):
            return False
        return (prev_k < prev_d) and (curr_k > curr_d)
    
    def check_stoch_bearish_crossover(self, prev_k: float, prev_d: float, 
                                      curr_k: float, curr_d: float) -> bool:
        """Check if Stochastic K cross below D (bearish)"""
        if not (prev_k and prev_d and curr_k and curr_d):
            return False
        return (prev_k > prev_d) and (curr_k < curr_d)
    
    def generate_signal(self, m1_candles: List[Dict], m5_candles: List[Dict], 
                       current_bid: float, current_ask: float, 
                       spread: float, max_spread: float) -> Tuple[Optional[str], float]:
        """
        Generate BUY/SELL signal dengan confidence score
        Returns: (signal_type, confidence_score)
        """
        if not (m1_candles and m5_candles):
            return None, 0
        
        # Extract price data
        m1_closes = [c['close'] for c in m1_candles]
        m1_highs = [c['high'] for c in m1_candles]
        m1_lows = [c['low'] for c in m1_candles]
        
        m5_closes = [c['close'] for c in m5_candles]
        m5_highs = [c['high'] for c in m5_candles]
        m5_lows = [c['low'] for c in m5_candles]
        
        # Calculate indicators
        ema_fast = self.calculate_ema(m5_closes, 5)
        ema_med = self.calculate_ema(m5_closes, 10)
        ema_slow = self.calculate_ema(m5_closes, 20)
        
        rsi_m1 = self.calculate_rsi(m1_closes, 14)
        rsi_m5 = self.calculate_rsi(m5_closes, 14)
        
        stoch_k_m1, stoch_d_m1 = self.calculate_stochastic(m1_highs, m1_lows, m1_closes)
        prev_stoch_k_m1, prev_stoch_d_m1 = None, None
        if len(m1_candles) >= 2:
            prev_m1_candles = m1_candles[-2:-1]
            if prev_m1_candles:
                prev_m1_closes = [c['close'] for c in prev_m1_candles]
                prev_m1_highs = [c['high'] for c in prev_m1_candles]
                prev_m1_lows = [c['low'] for c in prev_m1_candles]
                prev_stoch_k_m1, prev_stoch_d_m1 = self.calculate_stochastic(
                    prev_m1_highs, prev_m1_lows, prev_m1_closes
                )
        
        atr_m5 = self.calculate_atr(m5_highs, m5_lows, m5_closes)
        
        # Hitung confidence score dengan bobot
        confidence = 0
        signal_type = None
        
        # Cek SPREAD filter
        if spread > max_spread:
            return None, 0
        
        # BUY Conditions
        bullish_ema = self.check_bullish_ema(ema_fast, ema_med, ema_slow)
        rsi_oversold = self.check_rsi_oversold(rsi_m1, 30)
        stoch_oversold = self.check_stoch_oversold(stoch_k_m1, stoch_d_m1, 20)
        stoch_crossover = self.check_stoch_bullish_crossover(
            prev_stoch_k_m1, prev_stoch_d_m1, stoch_k_m1, stoch_d_m1
        ) if prev_stoch_k_m1 is not None else False
        
        buy_score = 0
        if bullish_ema:
            buy_score += 25
        if rsi_oversold:
            buy_score += 20
        if stoch_oversold:
            buy_score += 20
        if stoch_crossover:
            buy_score += 30
        buy_score += 5  # Base score
        
        # SELL Conditions
        bearish_ema = self.check_bearish_ema(ema_fast, ema_med, ema_slow)
        rsi_overbought = self.check_rsi_overbought(rsi_m1, 70)
        stoch_overbought = self.check_stoch_overbought(stoch_k_m1, stoch_d_m1, 80)
        stoch_bearish_crossover = self.check_stoch_bearish_crossover(
            prev_stoch_k_m1, prev_stoch_d_m1, stoch_k_m1, stoch_d_m1
        ) if prev_stoch_k_m1 is not None else False
        
        sell_score = 0
        if bearish_ema:
            sell_score += 25
        if rsi_overbought:
            sell_score += 20
        if stoch_overbought:
            sell_score += 20
        if stoch_bearish_crossover:
            sell_score += 30
        sell_score += 5  # Base score
        
        # Tentukan signal berdasarkan score
        if buy_score > sell_score and buy_score >= 40:
            confidence = buy_score
            signal_type = "BUY"
        elif sell_score > buy_score and sell_score >= 40:
            confidence = sell_score
            signal_type = "SELL"
        
        return signal_type, min(confidence, 100)
    
    def calculate_sl_tp(self, entry_price: float, signal_type: str, 
                       atr: Optional[float], default_sl_pips: float,
                       default_tp_pips: float, tp_rr_ratio: float,
                       sl_atr_multiplier: float) -> Tuple[float, float]:
        """
        Calculate SL dan TP based on ATR atau default
        """
        if signal_type == "BUY":
            if atr:
                sl = entry_price - (atr * sl_atr_multiplier)
            else:
                sl = entry_price - (default_sl_pips * 0.01)
            
            sl_distance = entry_price - sl
            tp = entry_price + (sl_distance * tp_rr_ratio)
        else:  # SELL
            if atr:
                sl = entry_price + (atr * sl_atr_multiplier)
            else:
                sl = entry_price + (default_sl_pips * 0.01)
            
            sl_distance = sl - entry_price
            tp = entry_price - (sl_distance * tp_rr_ratio)
        
        return sl, tp
