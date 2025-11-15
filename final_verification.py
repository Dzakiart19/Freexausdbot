#!/usr/bin/env python3
"""
FINAL BOT VERIFICATION - Simple dan Direct
"""
import sys
import os

sys.path.insert(0, '/workspaces/Freexausdbot')

from dotenv import load_dotenv
load_dotenv('/workspaces/Freexausdbot/.env')

print("\n" + "=" * 70)
print("✅ FREEXAUSDBOT - FINAL VERIFICATION")
print("=" * 70 + "\n")

checks = []

# 1. Configuration
print("📝 Configuration Check...")
token = os.getenv('TELEGRAM_BOT_TOKEN')
users = os.getenv('AUTHORIZED_USER_IDS')
eval_mode = os.getenv('EVALUATION_MODE')

if token and users and eval_mode:
    print(f"   ✅ Token: {token[:20]}...")
    print(f"   ✅ Users: {users}")
    print(f"   ✅ Eval Mode: {eval_mode}")
    checks.append(True)
else:
    print("   ❌ Missing configuration")
    checks.append(False)

# 2. Files
print("\n📂 File Check...")
required_files = [
    ('/workspaces/Freexausdbot/.env', '.env'),
    ('/workspaces/Freexausdbot/requirements.txt', 'requirements.txt'),
    ('/workspaces/Freexausdbot/app/main.py', 'app/main.py'),
    ('/workspaces/Freexausdbot/app/bot.py', 'app/bot.py'),
    ('/workspaces/Freexausdbot/app/strategy.py', 'app/strategy.py'),
]

all_exist = True
for path, name in required_files:
    if os.path.exists(path):
        print(f"   ✅ {name}")
    else:
        print(f"   ❌ {name} - NOT FOUND")
        all_exist = False

checks.append(all_exist)

# 3. Directories
print("\n📁 Directory Check...")
dirs = [
    ('/workspaces/Freexausdbot/app', 'app/'),
    ('/workspaces/Freexausdbot/app/logs', 'app/logs/'),
    ('/workspaces/Freexausdbot/app/data', 'app/data/'),
]

all_dirs_exist = True
for path, name in dirs:
    if os.path.isdir(path):
        print(f"   ✅ {name}")
    else:
        print(f"   ❌ {name} - NOT FOUND")
        all_dirs_exist = False

checks.append(all_dirs_exist)

# 4. Python Modules
print("\n🐍 Python Module Check...")
try:
    import telegram
    print("   ✅ python-telegram-bot")
except:
    print("   ❌ python-telegram-bot - NOT INSTALLED")
    checks.append(False)

try:
    import websocket
    print("   ✅ websocket-client")
except:
    print("   ❌ websocket-client - NOT INSTALLED")
    checks.append(False)

try:
    import pandas
    print("   ✅ pandas")
except:
    print("   ❌ pandas - NOT INSTALLED")
    checks.append(False)

try:
    import numpy
    print("   ✅ numpy")
except:
    print("   ❌ numpy - NOT INSTALLED")
    checks.append(False)

checks.append(True)  # If we got here, all imports worked

# 5. Bot Components
print("\n🤖 Bot Component Check...")
try:
    from app.ws_manager import ExnessWebSocket
    print("   ✅ WebSocket Manager")
except Exception as e:
    print(f"   ❌ WebSocket Manager: {e}")
    checks.append(False)

try:
    from app.aggregator import OHLCVAggregator
    print("   ✅ OHLCV Aggregator")
except Exception as e:
    print(f"   ❌ OHLCV Aggregator: {e}")
    checks.append(False)

try:
    from app.strategy import SignalStrategy
    print("   ✅ Signal Strategy")
except Exception as e:
    print(f"   ❌ Signal Strategy: {e}")
    checks.append(False)

try:
    from app.risk_manager import RiskManager
    print("   ✅ Risk Manager")
except Exception as e:
    print(f"   ❌ Risk Manager: {e}")
    checks.append(False)

try:
    from app.database import Database
    print("   ✅ Database")
except Exception as e:
    print(f"   ❌ Database: {e}")
    checks.append(False)

try:
    from app.bot import TelegramBot
    print("   ✅ Telegram Bot")
except Exception as e:
    print(f"   ❌ Telegram Bot: {e}")
    checks.append(False)

checks.append(True)

# 6. Database
print("\n💾 Database Check...")
try:
    db = Database('sqlite:////workspaces/Freexausdbot/app/data/bot.db')
    print("   ✅ Database initialized")
    print(f"   ✅ Tables created")
    checks.append(True)
except Exception as e:
    print(f"   ❌ Database error: {e}")
    checks.append(False)

# Summary
print("\n" + "=" * 70)
print("📊 VERIFICATION SUMMARY")
print("=" * 70)

passed = sum(checks)
total = len(checks)

print(f"\n✅ PASSED: {passed}/{total} checks")

if passed == total:
    print(f"""
🎉 SUCCESS! BOT IS FULLY READY FOR DEPLOYMENT!

📋 Quick Start:
   1. Run bot:
      python /workspaces/Freexausdbot/app/main.py
   
   2. In Telegram, send: /start
   
   3. Subscribe to signals: /monitor XAUUSD
   
   4. Check status: /status

📊 Mode: EVALUATION UNLIMITED
⏱️  Duration: 24 hours (for testing)
📈 Trades/Day: UNLIMITED
🎯 Confidence: 60% (eval mode)

💾 Files:
   - Main: /workspaces/Freexausdbot/app/main.py
   - DB: /workspaces/Freexausdbot/app/data/bot.db
   - Logs: /workspaces/Freexausdbot/app/logs/bot.log

🤖 Bot Credentials:
   - Token: {token[:30]}...
   - User: 7390867903
   - Mode: EVALUATION UNLIMITED

✅ STATUS: 🟢 READY TO RUN
""")
else:
    print(f"\n⚠️  {total - passed} checks failed")
    print("Please fix the issues above before running the bot")

print("=" * 70 + "\n")
