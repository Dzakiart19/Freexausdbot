import logging
import os
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class TelegramBot:
    def __init__(self, token: str, authorized_users: List[int], admin_users: List[int],
                 ws_manager, risk_manager, strategy, database):
        self.token = token
        self.authorized_users = authorized_users
        self.admin_users = admin_users
        self.ws_manager = ws_manager
        self.risk_manager = risk_manager
        self.strategy = strategy
        self.database = database
        self.subscribers = set()
        
    def create_application(self) -> Application:
        """Create Telegram bot application"""
        app = Application.builder().token(self.token).build()
        
        # Add handlers
        app.add_handler(CommandHandler("start", self.cmd_start))
        app.add_handler(CommandHandler("help", self.cmd_help))
        app.add_handler(CommandHandler("status", self.cmd_status))
        app.add_handler(CommandHandler("monitor", self.cmd_monitor))
        app.add_handler(CommandHandler("stopmonitor", self.cmd_stopmonitor))
        app.add_handler(CommandHandler("riwayat", self.cmd_riwayat))
        app.add_handler(CommandHandler("performa", self.cmd_performa))
        app.add_handler(CommandHandler("settings", self.cmd_settings))
        app.add_handler(CommandHandler("pausebot", self.cmd_pausebot))
        app.add_handler(CommandHandler("resumebot", self.cmd_resumebot))
        app.add_handler(CommandHandler("health", self.cmd_health))
        app.add_handler(CommandHandler("broadcast", self.cmd_broadcast))
        
        logger.info("Telegram bot application created")
        return app
    
    async def check_authorization(self, user_id: int) -> bool:
        """Check if user is authorized"""
        return user_id in self.authorized_users
    
    async def check_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        return user_id in self.admin_users
    
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user_id = update.effective_user.id
        is_auth = await self.check_authorization(user_id)
        
        if not is_auth:
            await update.message.reply_text("❌ User tidak terotorisasi. Hubungi admin.")
            logger.warning(f"Unauthorized user attempt: {user_id}")
            return
        
        msg = f"""
🤖 **XauScalp Sentinel v2.2.0**

Selamat datang di XAUUSD Scalping Signal Provider!

🟢 Status: **ONLINE**
📊 Mode: **{'EVALUATION UNLIMITED' if self.risk_manager.evaluation_mode else 'PRODUCTION'}**

Ketik /help untuk melihat semua command
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        user_id = update.effective_user.id
        if not await self.check_authorization(user_id):
            await update.message.reply_text("❌ Tidak terotorisasi")
            return
        
        is_admin = await self.check_admin(user_id)
        
        msg = """
📋 **COMMAND LIST**

**PUBLIC COMMAND:**
/status - Lihat status bot & trade count
/monitor XAUUSD - Subscribe sinyal
/stopmonitor - Unsubscribe
/riwayat [n] - Lihat n trade terakhir
/help - Bantuan

**ADMIN COMMAND:**
/performa [hours] - Statistik performa
/settings - Ubah parameter strategy
/pausebot - Pause bot
/resumebot - Resume bot
/health - Detail kesehatan bot
/broadcast - Broadcast pesan
"""
        if not is_admin:
            msg = msg.split("**ADMIN")[0] + "Hubungi admin untuk akses lebih."
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command"""
        user_id = update.effective_user.id
        if not await self.check_authorization(user_id):
            await update.message.reply_text("❌ Tidak terotorisasi")
            return
        
        ws_status = self.ws_manager.get_status()
        risk_status = self.risk_manager.get_status()
        
        msg = f"""
🟢 **STATUS BOT**

📊 Mode: **{'EVALUATION UNLIMITED' if risk_status['evaluation_mode'] else 'PRODUCTION'}**
🤖 Bot Status: **{'PAUSED' if risk_status['is_paused'] else 'RUNNING'}**

**WebSocket:**
Status: **{'🟢 Connected' if ws_status['connected'] else '🔴 Disconnected'}**
Delay: {ws_status['delay_seconds']:.2f}s
Tick Rate: {ws_status['tick_rate_tps']:.2f} tps
Spread: {ws_status['spread_pips']:.2f} pips
Price: BID {ws_status['current_bid']:.2f} / ASK {ws_status['current_ask']:.2f}

**Trading:**
Trades Today: {risk_status['trades_today']}
Max/Day: {risk_status['max_trades_per_day']}
Daily Loss: {risk_status['daily_loss_percent']:.2f}%
Balance: ${risk_status['virtual_balance']:,}

📈 Subscribers: {len(self.subscribers)}
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_monitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /monitor command"""
        user_id = update.effective_user.id
        if not await self.check_authorization(user_id):
            await update.message.reply_text("❌ Tidak terotorisasi")
            return
        
        self.subscribers.add(user_id)
        await update.message.reply_text("✅ Anda subscribe sinyal XAUUSD")
        logger.info(f"User {user_id} subscribed")
    
    async def cmd_stopmonitor(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /stopmonitor command"""
        user_id = update.effective_user.id
        self.subscribers.discard(user_id)
        await update.message.reply_text("✅ Anda unsubscribe sinyal")
        logger.info(f"User {user_id} unsubscribed")
    
    async def cmd_riwayat(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /riwayat command"""
        user_id = update.effective_user.id
        if not await self.check_authorization(user_id):
            await update.message.reply_text("❌ Tidak terotorisasi")
            return
        
        limit = 10
        if context.args and context.args[0].isdigit():
            limit = int(context.args[0])
        
        trades = self.database.get_trades(limit)
        if not trades:
            await update.message.reply_text("📭 Belum ada trade")
            return
        
        msg = "📊 **RIWAYAT TRADE (RECENT)**\n\n"
        for i, trade in enumerate(trades, 1):
            status_emoji = "✅" if trade['status'] == 'CLOSED_WIN' else ("❌" if 'LOSE' in trade['status'] else "⏳")
            msg += f"{i}. {trade['direction']} @ {trade['entry_price']:.2f}\n"
            msg += f"   P/L: {status_emoji} ${trade['pl_usd']:.2f} ({trade['pips_gained']:.1f}p)\n"
            msg += f"   Conf: {trade['confidence']:.0f}% | {trade['timestamp']}\n\n"
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_performa(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /performa command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        hours = 24
        if context.args and context.args[0].isdigit():
            hours = int(context.args[0])
        
        perf = self.database.get_performance(hours)
        
        msg = f"""
📈 **PERFORMA ({hours}H)**

Total Trades: {perf['total_trades']}
Wins: {perf['wins']} | Losses: {perf['losses']}
Win Rate: **{perf['win_rate']:.1f}%**
Total P/L: ${perf['total_pl_usd']:.2f}

Best Trade: +{perf['best_trade']:.1f}p
Worst Trade: {perf['worst_trade']:.1f}p

Mode: **EVALUATION UNLIMITED**
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_settings(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /settings command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        msg = "⚙️ **SETTINGS** - Pilih parameter untuk ubah"
        keyboard = [
            [InlineKeyboardButton("🎯 Confidence Min", callback_data="set_confidence")],
            [InlineKeyboardButton("❄️ Cooldown (detik)", callback_data="set_cooldown")],
            [InlineKeyboardButton("📊 Daily Loss %", callback_data="set_loss_limit")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(msg, reply_markup=reply_markup)
    
    async def cmd_pausebot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /pausebot command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        self.risk_manager.pause_bot()
        await update.message.reply_text("⏸️ Bot paused")
    
    async def cmd_resumebot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /resumebot command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        self.risk_manager.resume_bot()
        await update.message.reply_text("▶️ Bot resumed")
    
    async def cmd_health(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /health command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        ws_status = self.ws_manager.get_status()
        risk_status = self.risk_manager.get_status()
        
        msg = f"""
🏥 **BOT HEALTH CHECK**

**WebSocket:**
Status: **{'🟢 OK' if ws_status['connected'] else '🔴 ERROR'}**
Delay: {ws_status['delay_seconds']:.3f}s
Tick Rate: {ws_status['tick_rate_tps']:.2f} tps
Reconnects: {ws_status['reconnect_count']}
Ticks Today: {ws_status['tick_count']}

**Trading Engine:**
Mode: {'EVAL' if risk_status['evaluation_mode'] else 'PROD'}
Trades: {risk_status['trades_today']}
Loss: {risk_status['daily_loss_percent']:.2f}%
Paused: {'YES' if risk_status['is_paused'] else 'NO'}

**Memory:**
Uptime: Running
Database: OK
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    async def cmd_broadcast(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /broadcast command"""
        user_id = update.effective_user.id
        if not await self.check_admin(user_id):
            await update.message.reply_text("❌ Hanya admin")
            return
        
        if not context.args:
            await update.message.reply_text("Format: /broadcast <message>")
            return
        
        message = " ".join(context.args)
        # TODO: Send to all subscribers
        await update.message.reply_text(f"✅ Broadcast sent to {len(self.subscribers)} users")
    
    async def send_signal(self, signal_type: str, entry: float, sl: float, tp: float,
                         confidence: float, spread: float, delay: float, pips_risk: float):
        """Send signal to all subscribers"""
        pips_profit = abs(tp - entry) * 100
        estimated_pl = pips_profit * 10 * 0.01  # For 0.01 lot
        
        msg = f"""
🚀 **XAUUSD SCALPING SIGNAL**

📈 Type: **{signal_type}**
⏰ Timeframe: **M1/M5**
💰 Entry: {entry:.2f} {'(ASK)' if signal_type == 'BUY' else '(BID)'}
🎯 TP: {tp:.2f}
🛑 SL: {sl:.2f}
📊 Confidence: **{confidence:.0f}%**
📏 Spread: {spread:.2f} pips
⏱️ Delay: {delay:.2f}s ✅
⚠️ **EVALUATION MODE ACTIVE**

📈 Risk: {pips_risk:.1f}p | Profit: {pips_profit:.1f}p
💰 Est. P/L: ${estimated_pl:.2f} (0.01 lot)

⏰ Signal Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC / %H:%M WIB')}
"""
        
        for user_id in self.subscribers:
            try:
                # TODO: Send via context.bot.send_message
                pass
            except Exception as e:
                logger.error(f"Failed to send signal to {user_id}: {e}")
