import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RiskManager:
    def __init__(self):
        self.evaluation_mode = os.getenv('EVALUATION_MODE', 'false').lower() == 'true'
        self.virtual_balance = 1000000  # Representasi modal
        self.trades_today = 0
        self.daily_loss_usd = 0
        self.last_signal_time = 0
        self.is_paused = False
        self.daily_loss_list = []
        self.trades_list = []
        
    def can_generate_signal(self, current_delay: float, min_signal_confidence: float,
                          signal_confidence: float) -> Tuple[bool, str]:
        """
        Check all risk conditions sebelum generate signal
        Returns: (can_generate, reason)
        """
        import time
        
        # 1. DELAY CHECK (selalu aktif)
        max_delay = float(os.getenv('MAX_TICK_DELAY_SECONDS', 3.0))
        if current_delay > max_delay:
            return False, f"Delay too high: {current_delay:.2f}s > {max_delay}s"
        
        # 2. BOT PAUSE CHECK
        if self.is_paused:
            return False, "Bot is paused"
        
        # 3. DAILY LOSS CHECK (selalu aktif)
        if self.evaluation_mode:
            daily_loss_limit = float(os.getenv('DAILY_LOSS_PERCENT_EVAL', 5.0))
        else:
            daily_loss_limit = float(os.getenv('DAILY_LOSS_PERCENT', 3.0))
        
        daily_loss_percent = (self.daily_loss_usd / self.virtual_balance) * 100
        if daily_loss_percent > daily_loss_limit:
            logger.warning(f"Daily loss limit hit: {daily_loss_percent:.2f}% > {daily_loss_limit}%")
            return False, f"Daily loss limit exceeded: {daily_loss_percent:.2f}%"
        
        # 4. COOLDOWN CHECK
        if self.evaluation_mode:
            cooldown = float(os.getenv('SIGNAL_COOLDOWN_SECONDS_EVAL', 60))
        else:
            cooldown = float(os.getenv('SIGNAL_COOLDOWN_SECONDS', 180))
        
        if time.time() - self.last_signal_time < cooldown:
            return False, f"Cooldown active: {time.time() - self.last_signal_time:.0f}s < {cooldown}s"
        
        # 5. MAX TRADES CHECK (skip jika eval mode)
        if not self.evaluation_mode:
            max_trades = int(os.getenv('MAX_TRADES_PER_DAY', 5))
            if self.trades_today >= max_trades:
                logger.warning(f"Max trades per day exceeded: {self.trades_today} >= {max_trades}")
                return False, f"Max trades per day exceeded: {self.trades_today}/{max_trades}"
        
        # 6. CONFIDENCE THRESHOLD CHECK
        if self.evaluation_mode:
            min_conf = float(os.getenv('MIN_SIGNAL_CONFIDENCE_EVAL', 60.0))
        else:
            min_conf = float(os.getenv('MIN_SIGNAL_CONFIDENCE', 70.0))
        
        if signal_confidence < min_conf:
            return False, f"Confidence too low: {signal_confidence:.0f}% < {min_conf}%"
        
        return True, "OK"
    
    def record_signal(self):
        """Record when signal is generated"""
        import time
        self.last_signal_time = time.time()
        self.trades_today += 1
    
    def record_trade_result(self, pips_gained: float, lot_size: float = 0.01):
        """Record trade result"""
        # Convert pips to USD (assume 1 pip = $10 per lot for XAUUSD)
        pl_usd = pips_gained * 10 * lot_size
        self.daily_loss_usd += pl_usd
        self.trades_list.append({
            'timestamp': datetime.now(),
            'pips': pips_gained,
            'pl_usd': pl_usd
        })
        
        if pl_usd < 0:
            self.daily_loss_list.append(abs(pl_usd))
    
    def get_status(self) -> Dict:
        """Get risk manager status"""
        daily_loss_percent = (abs(self.daily_loss_usd) / self.virtual_balance) * 100 if self.daily_loss_usd < 0 else 0
        
        return {
            'evaluation_mode': self.evaluation_mode,
            'trades_today': self.trades_today,
            'daily_loss_usd': self.daily_loss_usd,
            'daily_loss_percent': daily_loss_percent,
            'is_paused': self.is_paused,
            'virtual_balance': self.virtual_balance,
            'max_trades_per_day': 'UNLIMITED' if self.evaluation_mode else os.getenv('MAX_TRADES_PER_DAY', 5)
        }
    
    def pause_bot(self):
        """Pause bot"""
        self.is_paused = True
        logger.warning("Bot paused")
    
    def resume_bot(self):
        """Resume bot"""
        self.is_paused = False
        logger.info("Bot resumed")
    
    def reset_daily_stats(self):
        """Reset daily statistics"""
        self.trades_today = 0
        self.daily_loss_usd = 0
        self.daily_loss_list = []
        self.trades_list = []
        logger.info("Daily stats reset")
    
    def calculate_win_rate(self) -> float:
        """Calculate win rate dari trades today"""
        if not self.trades_list:
            return 0
        
        wins = sum(1 for t in self.trades_list if t['pl_usd'] > 0)
        return (wins / len(self.trades_list)) * 100 if self.trades_list else 0
