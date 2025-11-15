import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class OHLCVAggregator:
    def __init__(self, pair: str = "XAUUSD"):
        self.pair = pair
        self.tick_buffer = []
        self.ohlcv_cache: Dict[str, List[Dict]] = {}  # {timeframe: [candles]}
        
    def add_tick(self, bid: float, ask: float, timestamp: float):
        """Tambahkan tick ke buffer"""
        mid_price = (bid + ask) / 2
        self.tick_buffer.append({
            "timestamp": timestamp,
            "bid": bid,
            "ask": ask,
            "price": mid_price
        })
        
    def aggregate_to_timeframe(self, timeframe: str = "M1") -> Optional[Dict]:
        """
        Aggregate tick buffer menjadi OHLCV candlestick
        timeframe: M1, M5, M15, H1
        """
        if not self.tick_buffer:
            return None
        
        # Convert timeframe ke seconds
        timeframe_seconds = self._get_timeframe_seconds(timeframe)
        
        # Group ticks by timeframe
        df = pd.DataFrame(self.tick_buffer)
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        df.set_index('timestamp', inplace=True)
        
        # Resample to OHLCV
        ohlcv = df['price'].resample(f'{timeframe_seconds}S').agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last',
            'volume': 'count'
        })
        
        if ohlcv.empty or ohlcv.iloc[-1]['volume'] == 0:
            return None
        
        last_candle = ohlcv.iloc[-1]
        return {
            "timeframe": timeframe,
            "timestamp": ohlcv.index[-1].timestamp(),
            "open": float(last_candle['open']),
            "high": float(last_candle['high']),
            "low": float(last_candle['low']),
            "close": float(last_candle['close']),
            "volume": int(last_candle['volume'])
        }
    
    def get_recent_candles(self, timeframe: str = "M1", count: int = 20) -> List[Dict]:
        """Ambil recent candles dari cache"""
        if timeframe not in self.ohlcv_cache:
            return []
        
        return self.ohlcv_cache[timeframe][-count:]
    
    def update_cache(self, timeframe: str, candle: Dict):
        """Update cache dengan candle baru"""
        if timeframe not in self.ohlcv_cache:
            self.ohlcv_cache[timeframe] = []
        
        # Cek jika candle sudah ada (update) atau baru (append)
        if self.ohlcv_cache[timeframe] and self.ohlcv_cache[timeframe][-1]["timestamp"] == candle["timestamp"]:
            self.ohlcv_cache[timeframe][-1] = candle
        else:
            self.ohlcv_cache[timeframe].append(candle)
            
        # Keep only last 100 candles per timeframe untuk memory efficiency
        if len(self.ohlcv_cache[timeframe]) > 100:
            self.ohlcv_cache[timeframe] = self.ohlcv_cache[timeframe][-100:]
    
    def clear_old_ticks(self, keep_seconds: int = 300):
        """Clear old ticks dari buffer"""
        current_time = datetime.now().timestamp()
        self.tick_buffer = [t for t in self.tick_buffer if current_time - t["timestamp"] < keep_seconds]
    
    @staticmethod
    def _get_timeframe_seconds(timeframe: str) -> int:
        """Convert timeframe string ke seconds"""
        multiplier = int(timeframe[:-1]) if timeframe[:-1].isdigit() else 1
        unit = timeframe[-1]
        
        if unit == 'M':
            return multiplier * 60
        elif unit == 'H':
            return multiplier * 3600
        elif unit == 'D':
            return multiplier * 86400
        else:
            return 60  # Default M1
