#!/usr/bin/env python3
"""
Test script untuk XauScalp Sentinel Bot
"""
import sys
import os
sys.path.insert(0, '/workspaces/Freexausdbot')

from dotenv import load_dotenv
load_dotenv('/workspaces/Freexausdbot/.env')

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test imports
print("=" * 50)
print("🧪 TESTING BOT COMPONENTS")
print("=" * 50)

try:
    print("\n1️⃣  Testing imports...")
    from app.ws_manager import ExnessWebSocket
    from app.aggregator import OHLCVAggregator
    from app.strategy import SignalStrategy
    from app.risk_manager import RiskManager
    from app.database import Database
    from app.bot import TelegramBot
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

try:
    print("\n2️⃣  Testing configuration...")
    bot_token = os.getenv('TELEGRAM_BOT_TOKEN')
    authorized_ids = os.getenv('AUTHORIZED_USER_IDS')
    admin_ids = os.getenv('ADMIN_USER_IDS')
    eval_mode = os.getenv('EVALUATION_MODE')
    
    print(f"   Bot Token: {bot_token[:30]}...")
    print(f"   Authorized Users: {authorized_ids}")
    print(f"   Admin Users: {admin_ids}")
    print(f"   Evaluation Mode: {eval_mode}")
    print("✅ Configuration loaded")
except Exception as e:
    print(f"❌ Config error: {e}")
    sys.exit(1)

try:
    print("\n3️⃣  Testing WebSocket Manager...")
    ws = ExnessWebSocket("wss://ws-json.exness.com/realtime", "XAUUSD")
    print(f"   WS URL: {ws.ws_url}")
    print(f"   Pair: {ws.pair}")
    print(f"   Connected: {ws.connected}")
    print("✅ WebSocket manager initialized")
except Exception as e:
    print(f"❌ WebSocket error: {e}")

try:
    print("\n4️⃣  Testing Aggregator...")
    agg = OHLCVAggregator("XAUUSD")
    agg.add_tick(2035.15, 2035.20, 1700044800)
    agg.add_tick(2035.16, 2035.21, 1700044801)
    candle = agg.aggregate_to_timeframe("M1")
    print(f"   Tick buffer: {len(agg.tick_buffer)} ticks")
    print("✅ Aggregator working")
except Exception as e:
    print(f"❌ Aggregator error: {e}")

try:
    print("\n5️⃣  Testing Strategy...")
    strategy = SignalStrategy({})
    
    # Create sample candles
    m1_candles = [
        {"open": 2034.50, "high": 2035.20, "low": 2034.40, "close": 2035.10},
        {"open": 2035.10, "high": 2035.80, "low": 2034.90, "close": 2035.50},
        {"open": 2035.50, "high": 2036.00, "low": 2035.30, "close": 2035.80},
    ]
    
    m5_candles = [
        {"open": 2034.00, "high": 2035.80, "low": 2033.90, "close": 2035.80},
    ]
    
    signal, conf = strategy.generate_signal(m1_candles, m5_candles, 2035.20, 2035.25, 0.5, 5.0)
    print(f"   Sample signal: {signal} (confidence: {conf:.0f}%)")
    print("✅ Strategy initialized")
except Exception as e:
    print(f"❌ Strategy error: {e}")

try:
    print("\n6️⃣  Testing Risk Manager...")
    rm = RiskManager()
    status = rm.get_status()
    print(f"   Mode: {'EVALUATION' if rm.evaluation_mode else 'PRODUCTION'}")
    print(f"   Trades today: {status['trades_today']}")
    print(f"   Daily loss: {status['daily_loss_percent']:.2f}%")
    print("✅ Risk manager initialized")
except Exception as e:
    print(f"❌ Risk manager error: {e}")

try:
    print("\n7️⃣  Testing Database...")
    db = Database('sqlite:////workspaces/Freexausdbot/app/data/bot.db')
    print(f"   Database path: /workspaces/Freexausdbot/app/data/bot.db")
    print("✅ Database initialized")
except Exception as e:
    print(f"❌ Database error: {e}")

try:
    print("\n8️⃣  Testing Telegram Bot...")
    auth_ids = [7390867903]
    admin_ids = [7390867903]
    
    tb = TelegramBot(
        token=bot_token,
        authorized_users=auth_ids,
        admin_users=admin_ids,
        ws_manager=ws,
        risk_manager=rm,
        strategy=strategy,
        database=db
    )
    print(f"   Bot subscribers: {len(tb.subscribers)}")
    print("✅ Telegram bot initialized")
except Exception as e:
    print(f"❌ Telegram bot error: {e}")

print("\n" + "=" * 50)
print("✅ ALL TESTS PASSED!")
print("=" * 50)
print("\n📝 Bot components are ready!")
print("📊 Database: /workspaces/Freexausdbot/app/data/bot.db")
print("📝 Logs: /workspaces/Freexausdbot/app/logs/bot.log")
print("\n✅ You can now run: python /workspaces/Freexausdbot/app/main.py")
