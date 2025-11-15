import asyncio
import json
import logging
import time
import websocket
from datetime import datetime
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)


class ExnessWebSocket:
    def __init__(self, ws_url: str, pair: str = "XAUUSD"):
        self.ws_url = ws_url
        self.pair = pair
        self.ws = None
        self.connected = False
        self.current_bid = None
        self.current_ask = None
        self.last_tick_time = time.time()
        self.tick_count = 0
        self.tick_count_last_minute = 0
        self.reconnect_count = 0
        self.reconnect_delay = 5
        self.max_reconnect_delay = 60
        
    def connect(self):
        """Koneksi ke WebSocket Exness"""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_open=self.on_open,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close
            )
            logger.info(f"Connecting to {self.ws_url}")
            self.ws.run_forever()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.handle_disconnect()
    
    def on_open(self, ws):
        """Callback saat koneksi berhasil"""
        self.connected = True
        self.reconnect_delay = 5
        logger.info("WebSocket connected")
        # Subscribe ke XAUUSD
        subscribe_msg = {
            "type": "subscribe",
            "pairs": [self.pair]
        }
        ws.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to {self.pair}")
    
    def on_message(self, ws, message):
        """Callback saat menerima pesan"""
        try:
            data = json.loads(message)
            if data.get("type") == "tick" and data.get("pair") == self.pair:
                self.current_bid = float(data.get("bid", 0))
                self.current_ask = float(data.get("ask", 0))
                self.last_tick_time = time.time()
                self.tick_count += 1
                self.tick_count_last_minute += 1
                logger.debug(f"Tick: BID={self.current_bid}, ASK={self.current_ask}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")
    
    def on_error(self, ws, error):
        """Callback saat error"""
        logger.error(f"WebSocket error: {error}")
    
    def on_close(self, ws, close_status_code, close_msg):
        """Callback saat koneksi ditutup"""
        self.connected = False
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.handle_disconnect()
    
    def handle_disconnect(self):
        """Handle disconnect dengan reconnect exponential backoff"""
        self.reconnect_count += 1
        logger.warning(f"Reconnect attempt #{self.reconnect_count}, delay {self.reconnect_delay}s")
        time.sleep(self.reconnect_delay)
        self.reconnect_delay = min(self.reconnect_delay * 2, self.max_reconnect_delay)
        self.connect()
    
    def get_current_delay(self) -> float:
        """Hitung delay tick saat ini"""
        return time.time() - self.last_tick_time
    
    def get_tick_rate(self) -> float:
        """Hitung tick rate (ticks per second)"""
        return self.tick_count_last_minute / 60.0 if self.tick_count_last_minute > 0 else 0
    
    def get_spread(self) -> float:
        """Hitung spread dalam pips (0.01 untuk XAUUSD)"""
        if self.current_bid and self.current_ask:
            return (self.current_ask - self.current_bid) / 0.01
        return 0
    
    def get_status(self) -> Dict:
        """Return status WebSocket"""
        return {
            "connected": self.connected,
            "current_bid": self.current_bid,
            "current_ask": self.current_ask,
            "delay_seconds": self.get_current_delay(),
            "tick_rate_tps": self.get_tick_rate(),
            "spread_pips": self.get_spread(),
            "tick_count": self.tick_count,
            "reconnect_count": self.reconnect_count
        }
