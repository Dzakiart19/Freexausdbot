import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_url: str):
        self.db_path = db_url.replace('sqlite:///', '')
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Tabel OHLCV Cache
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ohlcv_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timeframe TEXT NOT NULL,
                timestamp_utc INTEGER NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabel Trades
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id TEXT UNIQUE NOT NULL,
                ticker TEXT NOT NULL,
                direction TEXT,
                entry_price REAL,
                exit_price REAL,
                sl REAL,
                tp REAL,
                signal_timestamp TIMESTAMP,
                status TEXT DEFAULT 'OPEN',
                confidence REAL,
                pips_gained REAL,
                virtual_pl_usd REAL,
                is_evaluation_mode BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabel Bot State
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bot_state (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE NOT NULL,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Tabel WebSocket Health Log
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS ws_health_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                delay_ms REAL,
                status TEXT,
                message TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized: {self.db_path}")
    
    def add_ohlcv(self, timeframe: str, timestamp_utc: int, ohlcv: Dict):
        """Add OHLCV candle"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO ohlcv_cache (timeframe, timestamp_utc, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (timeframe, timestamp_utc, ohlcv['open'], ohlcv['high'], 
              ohlcv['low'], ohlcv['close'], ohlcv['volume']))
        
        conn.commit()
        conn.close()
    
    def add_trade(self, signal_id: str, ticker: str, direction: str, entry_price: float,
                  sl: float, tp: float, signal_timestamp: str, confidence: float,
                  is_eval_mode: bool):
        """Add new trade"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO trades (signal_id, ticker, direction, entry_price, sl, tp, 
                              signal_timestamp, status, confidence, is_evaluation_mode)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN', ?, ?)
        ''', (signal_id, ticker, direction, entry_price, sl, tp, 
              signal_timestamp, confidence, is_eval_mode))
        
        conn.commit()
        conn.close()
        logger.info(f"Trade added: {signal_id} {direction} @ {entry_price}")
    
    def update_trade_result(self, signal_id: str, exit_price: float, pips_gained: float,
                           pl_usd: float, status: str):
        """Update trade result"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE trades SET exit_price = ?, pips_gained = ?, virtual_pl_usd = ?,
                           status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE signal_id = ?
        ''', (exit_price, pips_gained, pl_usd, status, signal_id))
        
        conn.commit()
        conn.close()
        logger.info(f"Trade updated: {signal_id} {status} (P/L: ${pl_usd})")
    
    def get_trades(self, limit: int = 10) -> List[Dict]:
        """Get recent trades"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT signal_id, direction, entry_price, exit_price, pips_gained, 
                   virtual_pl_usd, status, signal_timestamp, confidence
            FROM trades ORDER BY created_at DESC LIMIT ?
        ''', (limit,))
        
        trades = []
        for row in cursor.fetchall():
            trades.append({
                'signal_id': row[0],
                'direction': row[1],
                'entry_price': row[2],
                'exit_price': row[3],
                'pips_gained': row[4],
                'pl_usd': row[5],
                'status': row[6],
                'timestamp': row[7],
                'confidence': row[8]
            })
        
        conn.close()
        return trades
    
    def get_performance(self, hours: int = 24) -> Dict:
        """Get performance stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get trades dari last N hours
        cursor.execute('''
            SELECT COUNT(*) as total,
                   SUM(CASE WHEN virtual_pl_usd > 0 THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN virtual_pl_usd < 0 THEN 1 ELSE 0 END) as losses,
                   SUM(virtual_pl_usd) as total_pl,
                   MAX(pips_gained) as best_trade,
                   MIN(pips_gained) as worst_trade
            FROM trades
            WHERE status = 'CLOSED_WIN' OR status = 'CLOSED_LOSE'
              AND is_evaluation_mode = 1
              AND created_at >= datetime('now', '-' || ? || ' hours')
        ''', (hours,))
        
        result = cursor.fetchone()
        conn.close()
        
        total_trades = result[0] or 0
        wins = result[1] or 0
        losses = result[2] or 0
        total_pl = result[3] or 0
        best_trade = result[4]
        worst_trade = result[5]
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': (wins / total_trades * 100) if total_trades > 0 else 0,
            'total_pl_usd': total_pl,
            'best_trade': best_trade,
            'worst_trade': worst_trade,
            'profit_factor': 1.0  # Will calculate from trades
        }
    
    def set_state(self, key: str, value: str):
        """Set bot state"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO bot_state (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (key, value))
        
        conn.commit()
        conn.close()
    
    def get_state(self, key: str) -> Optional[str]:
        """Get bot state"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT value FROM bot_state WHERE key = ?', (key,))
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def log_ws_health(self, delay_ms: float, status: str, message: str = ""):
        """Log WebSocket health"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO ws_health_log (delay_ms, status, message)
            VALUES (?, ?, ?)
        ''', (delay_ms, status, message))
        
        conn.commit()
        conn.close()
