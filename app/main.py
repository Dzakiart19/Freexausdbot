import asyncio
import logging
import os
import sys
import time
import threading
from datetime import datetime
from typing import Optional
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
    handlers=[
        logging.FileHandler('/workspaces/Freexausdbot/app/logs/bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Import modules
from app.ws_manager import ExnessWebSocket
from app.aggregator import OHLCVAggregator
from app.strategy import SignalStrategy
from app.risk_manager import RiskManager
from app.database import Database
from app.bot import TelegramBot


class BotOrchestrator:
    def __init__(self):
        logger.info("=" * 50)
        logger.info("XauScalp Sentinel v2.2.0 - BOT START")
        logger.info("=" * 50)
        
        # Initialize components
        self.ws_manager = ExnessWebSocket(
            ws_url=os.getenv('WS_URL', 'wss://ws-json.exness.com/realtime'),
            pair="XAUUSD"
        )
        
        self.aggregator = OHLCVAggregator("XAUUSD")
        
        self.strategy = SignalStrategy({
            'ema_fast': int(os.getenv('EMA_PERIODS_FAST', 5)),
            'ema_med': int(os.getenv('EMA_PERIODS_MED', 10)),
            'ema_slow': int(os.getenv('EMA_PERIODS_SLOW', 20)),
            'rsi_period': int(os.getenv('RSI_PERIOD', 14)),
            'atr_period': int(os.getenv('ATR_PERIOD', 14)),
        })
        
        self.risk_manager = RiskManager()
        
        self.database = Database(
            db_url=os.getenv('DATABASE_URL', 'sqlite:////workspaces/Freexausdbot/app/data/bot.db')
        )
        
        # Parse authorized users
        authorized_str = os.getenv('AUTHORIZED_USER_IDS', '').split(',')
        self.authorized_users = [int(uid.strip()) for uid in authorized_str if uid.strip()]
        
        admin_str = os.getenv('ADMIN_USER_IDS', '').split(',')
        self.admin_users = [int(uid.strip()) for uid in admin_str if uid.strip()]
        
        self.telegram_bot = TelegramBot(
            token=os.getenv('TELEGRAM_BOT_TOKEN'),
            authorized_users=self.authorized_users,
            admin_users=self.admin_users,
            ws_manager=self.ws_manager,
            risk_manager=self.risk_manager,
            strategy=self.strategy,
            database=self.database
        )
        
        self.last_m1_candle = None
        self.last_m5_candle = None
        self.m1_candles = []
        self.m5_candles = []
        self.running = True
        self.last_cleanup = time.time()
        
        logger.info(f"✅ Authorized users: {self.authorized_users}")
        logger.info(f"✅ Admin users: {self.admin_users}")
        logger.info(f"✅ Evaluation mode: {self.risk_manager.evaluation_mode}")
    
    def run_websocket(self):
        """Run WebSocket connection in background thread"""
        logger.info("Starting WebSocket connection...")
        try:
            self.ws_manager.connect()
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
    
    async def run_signal_loop(self):
        """Main signal generation loop"""
        logger.info("Starting signal generation loop...")
        
        while self.running:
            try:
                # Check WebSocket connection
                if not self.ws_manager.connected:
                    logger.warning("WebSocket disconnected, waiting...")
                    await asyncio.sleep(5)
                    continue
                
                # Get current price
                bid = self.ws_manager.current_bid
                ask = self.ws_manager.current_ask
                
                if not (bid and ask):
                    await asyncio.sleep(0.5)
                    continue
                
                # Add tick to aggregator
                current_time = time.time()
                self.aggregator.add_tick(bid, ask, current_time)
                
                # Aggregate M1 candle
                m1_candle = self.aggregator.aggregate_to_timeframe("M1")
                if m1_candle and (not self.last_m1_candle or m1_candle['timestamp'] != self.last_m1_candle['timestamp']):
                    self.aggregator.update_cache("M1", m1_candle)
                    self.m1_candles.append(m1_candle)
                    if len(self.m1_candles) > 50:
                        self.m1_candles = self.m1_candles[-50:]
                    self.last_m1_candle = m1_candle
                    logger.debug(f"M1 Candle: {m1_candle['close']:.2f}")
                
                # Aggregate M5 candle
                m5_candle = self.aggregator.aggregate_to_timeframe("M5")
                if m5_candle and (not self.last_m5_candle or m5_candle['timestamp'] != self.last_m5_candle['timestamp']):
                    self.aggregator.update_cache("M5", m5_candle)
                    self.m5_candles.append(m5_candle)
                    if len(self.m5_candles) > 50:
                        self.m5_candles = self.m5_candles[-50:]
                    self.last_m5_candle = m5_candle
                    logger.info(f"M5 Candle: {m5_candle['close']:.2f}")
                
                # Generate signals when we have enough candles
                if len(self.m1_candles) >= 2 and len(self.m5_candles) >= 2:
                    delay = self.ws_manager.get_current_delay()
                    spread = self.ws_manager.get_spread()
                    max_spread = float(os.getenv('MAX_SPREAD_PIPS', 5.0))
                    
                    # Get indicator thresholds
                    if self.risk_manager.evaluation_mode:
                        min_conf = float(os.getenv('MIN_SIGNAL_CONFIDENCE_EVAL', 60.0))
                    else:
                        min_conf = float(os.getenv('MIN_SIGNAL_CONFIDENCE', 70.0))
                    
                    # Generate signal
                    signal_type, confidence = self.strategy.generate_signal(
                        self.m1_candles, self.m5_candles, bid, ask, spread, max_spread
                    )
                    
                    # Check if we can generate signal
                    can_generate, reason = self.risk_manager.can_generate_signal(
                        delay, min_conf, confidence
                    )
                    
                    if signal_type and can_generate and confidence >= min_conf:
                        logger.info(f"✅ Signal: {signal_type} @ {ask:.2f} (Conf: {confidence:.0f}%)")
                        
                        # Calculate SL/TP
                        m5_high = [c['high'] for c in self.m5_candles]
                        m5_low = [c['low'] for c in self.m5_candles]
                        m5_close = [c['close'] for c in self.m5_candles]
                        
                        atr = self.strategy.calculate_atr(m5_high, m5_low, m5_close)
                        
                        entry = ask if signal_type == "BUY" else bid
                        sl, tp = self.strategy.calculate_sl_tp(
                            entry,
                            signal_type,
                            atr,
                            float(os.getenv('DEFAULT_SL_PIPS', 25.0)),
                            float(os.getenv('DEFAULT_TP_PIPS', 45.0)),
                            float(os.getenv('TP_RR_RATIO', 1.8)),
                            float(os.getenv('SL_ATR_MULTIPLIER', 1.5))
                        )
                        
                        # Calculate risk/reward
                        pips_risk = abs(entry - sl) * 100
                        pips_profit = abs(tp - entry) * 100
                        
                        # Record signal in database
                        signal_id = f"eval_{int(time.time() * 1000)}"
                        self.database.add_trade(
                            signal_id,
                            "XAUUSD",
                            signal_type,
                            entry,
                            sl,
                            tp,
                            datetime.now().isoformat(),
                            confidence,
                            self.risk_manager.evaluation_mode
                        )
                        
                        # Record in risk manager
                        self.risk_manager.record_signal()
                        
                        # Send signal to Telegram
                        await self.telegram_bot.send_signal(
                            signal_type,
                            entry,
                            sl,
                            tp,
                            confidence,
                            spread,
                            delay,
                            pips_risk
                        )
                    elif signal_type and not can_generate:
                        logger.debug(f"Signal blocked: {reason}")
                
                # Cleanup old ticks
                current_time = time.time()
                if current_time - self.last_cleanup > 300:  # Every 5 minutes
                    self.aggregator.clear_old_ticks()
                    self.last_cleanup = current_time
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Error in signal loop: {e}", exc_info=True)
                await asyncio.sleep(1)
    
    async def run_telegram_bot(self):
        """Run Telegram bot"""
        logger.info("Starting Telegram bot...")
        try:
            app = self.telegram_bot.create_application()
            await app.run_polling()
        except Exception as e:
            logger.error(f"Telegram bot error: {e}", exc_info=True)
    
    async def run_health_check(self):
        """Run health check periodically"""
        while self.running:
            try:
                ws_status = self.ws_manager.get_status()
                risk_status = self.risk_manager.get_status()
                
                delay = ws_status['delay_seconds']
                alert_threshold = float(os.getenv('ALERT_DELAY_THRESHOLD_SECONDS', 5.0))
                
                if delay > alert_threshold:
                    logger.warning(f"⚠️ High delay: {delay:.2f}s")
                    self.database.log_ws_health(delay * 1000, "HIGH_DELAY", f"Delay {delay:.2f}s")
                
                # Log health every 1 hour
                self.database.log_ws_health(delay * 1000, "OK", "Health check")
                
                # Log status every hour
                logger.info(f"📊 Status - Trades: {risk_status['trades_today']}, "
                          f"Loss: {risk_status['daily_loss_percent']:.2f}%, "
                          f"Delay: {delay:.2f}s")
                
                # Reset daily stats at midnight
                now = datetime.now()
                if now.hour == 0 and now.minute == 0:
                    logger.info("🔄 Resetting daily statistics...")
                    self.risk_manager.reset_daily_stats()
                
                await asyncio.sleep(3600)  # Check every hour
            
            except Exception as e:
                logger.error(f"Health check error: {e}")
                await asyncio.sleep(60)
    
    async def main(self):
        """Main async function"""
        # Start WebSocket in background thread
        ws_thread = threading.Thread(target=self.run_websocket, daemon=True)
        ws_thread.start()
        
        # Wait for WebSocket connection
        max_wait = 30
        waited = 0
        while not self.ws_manager.connected and waited < max_wait:
            logger.info("Waiting for WebSocket connection...")
            await asyncio.sleep(1)
            waited += 1
        
        if not self.ws_manager.connected:
            logger.error("❌ Failed to connect to WebSocket")
            return
        
        logger.info("✅ WebSocket connected!")
        
        # Run signal loop and Telegram bot concurrently
        try:
            await asyncio.gather(
                self.run_signal_loop(),
                self.run_telegram_bot(),
                self.run_health_check()
            )
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
            self.running = False
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.running = False


async def main():
    """Entry point"""
    orchestrator = BotOrchestrator()
    await orchestrator.main()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n👋 Bot shutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
