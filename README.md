# **BOT TELEGRAM XAUUSD SCALPING SIGNAL PROVIDER - SPESIFIKASI V2.2 (EVALUATION UNLIMITED MODE)**

**Update:** Mode evaluasi 24 jam dengan **unlimited trade count** untuk analisis win/lose rate, sementara **risk layer lain aktif** sebagai failsafe.

---

## **IDENTITAS PROYEK**
**Nama Bot:** `XauScalp Sentinel`  
**Versi:** 2.2.0-EVAL-UNLIMITED  
**Tujuan:** Signal Provider otomatis 24/7 untuk XAUUSD scalping M1/M5 dengan **mode evaluasi unlimited trade**  
**Target User:** Developer/Trader untuk **testing 24 jam pertama** (bukan live production)  
**Model Risiko:** High-frequency signal dengan **partial risk override** untuk evaluasi  
**Disclaimer:** Bot ini **TIDAK mengeksekusi trade**, hanya signal provider

---

## **1. ARSITEKTUR INTI & FILOSOFI**

### **1.1 Design Principles**
- **Zero Execution Guarantee:** Pure signal generator, tidak ada kode eksekusi trade atau integrasi MetaTrader API.
- **Real-Time First:** Semua sinyal dari **tick data realtime** WebSocket Exness dengan delay monitoring.
- **Evaluation Mode Override:** **Nonaktifkan trade count limit** untuk evaluasi win/lose rate 24 jam.
- **Failsafe Active:** **Daily loss limit, cooldown, spread filter, delay protection tetap aktif** untuk proteksi.
- **Signal-First Architecture:** Semua komponen bekerja secara *asynchronous* dan *non-blocking*.
- **Transparency:** Setiap sinyal mencantumkan `evaluation_mode=True` di pesan Telegram.

### **1.2 High-Level Flow (Eval Mode)**
```
[Exness WS Tick] → [Delay Check] → [OHLCV Agg] → [Signal Logic] 
→ [Skip Trade Count Check] → [Daily Loss Check] → [Cooldown Check] 
→ [Telegram Signal] → [Position Monitor] → [Result Log]
```

---

## **2. KONEKSI WEBSOCKET EXNESS - REALTIME FEED**

### **2.1 WebSocket Endpoint**
```python
WS_URL = "wss://ws-json.exness.com/realtime"
SUBSCRIBE_PAYLOAD = {"type": "subscribe", "pairs": ["XAUUSD"]}
```

### **2.2 Format Data Tick**
```json
{
  "type": "tick",
  "pair": "XAUUSD",
  "bid": 2035.15,
  "ask": 2035.20,
  "timestamp": 1700044800
}
```

### **2.3 WebSocket Manager (`ws_manager.py`)**

**Responsibilitas:**
- Connect, subscribe, parse tick data
- Hitung `delay = time.time() - timestamp` setiap tick
- Update in-memory cache: `current_bid`, `current_ask`, `last_tick_time`, `current_delay`
- **Skip tick** jika delay > `MAX_TICK_DELAY_SECONDS` (default 3 detik)
- Auto-reconnect dengan exponential backoff: `2^n * 5 detik` (max 60 detik)
- Alert admin jika disconnect > 30 detik atau delay > 5 detik

**Delay Metrics:**
```python
class ExnessWebSocket:
    def get_current_delay(self) -> float:
        return time.time() - self.last_tick_time
    
    def get_tick_rate(self) -> float:
        return self.tick_count_last_minute / 60.0
```

---

## **3. STRATEGI TRADING - UNLIMITED EVALUATION MODE**

### **3.1 Konfigurasi Utama**
```env
# STRATEGY PARAMETERS
EMA_PERIODS_FAST=5
EMA_PERIODS_MED=10
EMA_PERIODS_SLOW=20
RSI_PERIOD=14
RSI_OVERSOLD_LEVEL=30
RSI_OVERBOUGHT_LEVEL=70
STOCH_K_PERIOD=14
STOCH_D_PERIOD=3
STOCH_OVERSOLD_LEVEL=20
STOCH_OVERBOUGHT_LEVEL=80
ATR_PERIOD=14
SL_ATR_MULTIPLIER=1.5
DEFAULT_SL_PIPS=25.0
TP_RR_RATIO=1.8
DEFAULT_TP_PIPS=45.0
MAX_SPREAD_PIPS=5.0
MIN_SIGNAL_CONFIDENCE=70.0
```

### **3.2 Logika Signal (Tetap Sama)**
- **BUY:** EMA bullish (M5) + RSI oversold reversal (M1) + Stochastic cross-up (M1) + Volume spike + Spread < threshold
- **SELL:** Inverse
- **Confidence Score:** `SUM(bobot_terpenuhi) / 100` → Kirim hanya jika > `MIN_SIGNAL_CONFIDENCE`

### **3.3 Entry/SL/TP**
- **Entry Price:** Ask untuk BUY, Bid untuk SELL (real-time dari WS)
- **SL:** `Entry - (ATR_M5 * SL_ATR_MULTIPLIER)` atau `DEFAULT_SL_PIPS`
- **TP:** `Entry + (SL_distance * TP_RR_RATIO)` atau `DEFAULT_TP_PIPS`
- **Timestamp Signal:** Waktu candle close UTC (format: `2025-11-15 12:30:00 UTC / 19:30 WIB`)

---

## **4. RISK & ACCOUNT PROTECTION - EVALUATION MODE OVERRIDE**

### **4.1 Virtual Account State**
```python
virtual_balance = 1000000  # Representasi modal 500rb IDR
risk_per_trade = virtual_balance * (RISK_PER_TRADE_PERCENT / 100)  # Default 0.5% = 5.000 IDR
daily_loss_limit = virtual_balance * (DAILY_LOSS_PERCENT / 100)   # Default 3% = 30.000 IDR
```

### **4.2 Risk Layer Behavior di Eval Mode**

| Fitur | Production Mode | **Evaluation Mode** |
|-------|-----------------|---------------------|
| **Max Trades Per Day** | `MAX_TRADES_PER_DAY=5` | **UNLIMITED (override)** |
| **Daily Loss Limit** | Pause bot > 3% loss | **Pause bot > 5% loss** (lebih longgar) |
| **Signal Cooldown** | 180 detik | **60 detik** (lebih cepat) |
| **Max Concurrent** | 1 | **1 (tetap)** |
| **Spread Filter** | Active | **Active** |
| **Delay Protection** | Active | **Active** |
| **Confidence Threshold** | 70% | **60%** (lebih banyak sinyal) |

**Logika di Kode (`risk_manager.py`):**
```python
EVALUATION_MODE = os.getenv('EVALUATION_MODE', 'false').lower() == 'true'

def can_generate_signal():
    # 1. DELAY CHECK (selalu aktif)
    if ws_manager.get_current_delay() > float(os.getenv('MAX_TICK_DELAY_SECONDS', 3.0)):
        logger.warning(f"Signal paused: delay={ws_manager.get_current_delay():.2f}s")
        return False
    
    # 2. DAILY LOSS CHECK (selalu aktif)
    if daily_loss > float(os.getenv('DAILY_LOSS_PERCENT_EVAL', 5.0) if EVALUATION_MODE else os.getenv('DAILY_LOSS_PERCENT', 3.0)):
        alert_admin("⚠️ Daily loss limit hit in eval mode")
        return False
    
    # 3. COOLDOWN CHECK (adjust untuk eval)
    if time.time() - last_signal_time < (60 if EVALUATION_MODE else 180):
        return False
    
    # 4. MAX TRADES CHECK (skip jika eval mode)
    if not EVALUATION_MODE and trades_today >= int(os.getenv('MAX_TRADES_PER_DAY', 5)):
        return False
    
    # 5. OTHER CHECKS (confidence, spread, etc)
    return check_other_risk_rules()
```

### **4.3 Environment Variables untuk Eval Mode**
```bash
# PRODUCTION VALUES
MAX_TRADES_PER_DAY=5
DAILY_LOSS_PERCENT=3.0
SIGNAL_COOLDOWN_SECONDS=180
MIN_SIGNAL_CONFIDENCE=70.0

# EVALUATION MODE VALUES (aktif jika EVALUATION_MODE=true)
DAILY_LOSS_PERCENT_EVAL=5.0  # Lebih longgar
SIGNAL_COOLDOWN_SECONDS_EVAL=60  # Lebih cepat
MIN_SIGNAL_CONFIDENCE_EVAL=60.0  # Lebih banyak sinyal
```

---

## **5. TELEGRAM BOT INTERFACE - PERINTAH & OTORISASI**

### **5.1 Perintah Dasar (Semua User)**
- `/start`: Sambutan + cek otorisasi
- `/help`: Daftar semua command
- `/status`: Lihat status bot, **trade count hari ini**, **eval mode status**, delay, API health
- `/monitor XAUUSD`: Subscribe sinyal
- `/stopmonitor XAUUSD`: Unsubscribe
- `/riwayat [n]`: Lihat n trade terakhir (default 10)

### **5.2 Perintah Admin (User ID di `ADMIN_USER_IDS`)**
- `/performa [period]`: Statistik performa (total trades, win rate, profit factor, avg RR, max drawdown, **trades di eval mode**)
- `/settings`: Inline keyboard untuk ubah parameter strategy (real-time update env var)
- `/pausebot`: Pause semua sinyal baru (posisi terbuka tetap dimonitor)
- `/resumebot`: Resume bot
- `/forceclose <signal_id>`: Close virtual position manual
- `/health`: Detail WebSocket, delay, uptime, reconnect count
- `/broadcast <message>`: Kirim pesan ke semua subscriber

### **5.3 Format Pesan Sinyal (Eval Mode)**
```
🚀 XAUUSD SCALPING SIGNAL

📈 Tipe: BUY
⏰ Timeframe: M1/M5
💰 Entry: 2035.20 (ask)
🎯 TP: 2037.20 (+45 pips)
🛑 SL: 2032.70 (-25 pips)
📊 Confidence: 65%
📏 Spread: 3.2 pips
⏱️ Signal Time: 2025-11-15 12:30:00 UTC / 19:30 WIB
⏱️ Feed Delay: 0.15s ✅
⚠️ **EVALUATION MODE ACTIVE**

💰 Est. P/L: $0.45 (0.01 lot)
```

---

## **6. WEBSOCKET HEALTH MONITORING & DELAY ALERTING**

### **6.1 Metrics yang Di-track**
- **Connection Status:** Connected / Disconnected / Reconnecting
- **Last Tick Time:** Timestamp terakhir tick valid (Unix epoch)
- **Current Delay:** `time.time() - last_tick_time` (real-time)
- **Tick Rate:** Ticks per second (ideal: 1-5 tps untuk XAUUSD)
- **Reconnect Count:** Counter hari ini
- **Stale Tick Count:** Berapa tick yang di-skip karena delay tinggi

### **6.2 Telegram Alerts (Eval Mode)**
- **WARNING:** Reconnect > 30 detik
- **CRITICAL:** Tidak ada tick baru > 2 menit
- **HIGH DELAY:** `delay > ALERT_DELAY_THRESHOLD_SECONDS` (default 5 detik)
- **EVAL MODE ALERT:** Kirim setiap 6 jam: "📊 Eval mode: 45 signals generated, 28W 17L, win rate 62%"

### **6.3 Health Check Endpoint (`/health`)**
```python
{
  "status": "healthy",
  "mode": "evaluation",  # "production" jika EVALUATION_MODE=false
  "websocket": {
    "status": "connected",
    "last_tick_time": 1700044800,
    "delay_seconds": 0.85,
    "tick_rate_tps": 2.3,
    "reconnect_count_today": 1,
    "stale_ticks_skipped": 3
  },
  "trading": {
    "active_signals": 0,
    "trades_today": 47,  # Unlimited di eval mode
    "daily_loss_percent": 4.2,
    "is_paused": false
  }
}
```

---

## **7. PERSISTENSI & DATABASE**

### **7.1 SQLite Schema**
```python
# Tabel: ohlcv_cache
- id, timeframe, timestamp_utc, open, high, low, close, volume

# Tabel: trades
- id, signal_id, ticker, direction, entry_price, exit_price, sl, tp, 
  signal_timestamp, status, confidence, pips_gained, virtual_pl_usd,
  is_evaluation_mode  # BARU: flag untuk filter performa

# Tabel: bot_state
- key, value, updated_at

# Tabel: ws_health_log
- timestamp, delay_ms, status, message
```

### **7.2 Query untuk Analisis Evaluasi**
```sql
-- Hitung win rate 24 jam evaluasi
SELECT 
  COUNT(*) as total_trades,
  SUM(CASE WHEN status='CLOSED_WIN' THEN 1 ELSE 0 END) as wins,
  SUM(CASE WHEN status='CLOSED_LOSE' THEN 1 ELSE 0 END) as losses,
  ROUND(100.0 * wins / total_trades, 2) as win_rate,
  SUM(virtual_pl_usd) as total_pl
FROM trades
WHERE is_evaluation_mode = 1
  AND signal_timestamp >= datetime('now', '-24 hours');
```

---

## **8. LOGGING & OBSERVABILITY (Eval Mode)**

### **8.1 Log Format**
```python
[2025-11-15 12:30:02] [INFO] [strategy] Signal BUY generated (eval_mode=True, confidence=65%)
[2025-11-15 12:30:03] [INFO] [bot] Signal sent to Telegram: signal_id=eval_abc123
[2025-11-15 12:30:05] [WARNING] [risk] Daily loss: 4.8% (limit: 5.0%)
[2025-11-15 12:35:10] [INFO] [monitor] TP hit: +45 pips, win_rate=62% (eval)
[2025-11-15 13:00:00] [INFO] [summary] 1H eval: 8 signals, 5W 3L, +$2.40
```

### **8.2 Log Rotation**
- File: `/app/logs/bot.log` (mount persistent volume)
- Max: 10MB, backup 5 files
- Level: INFO console, WARNING/ERROR ke file + Telegram admin

---

## **9. ENVIRONMENT VARIABLES MASTERLIST (FINAL)**

```bash
# ========== CORE ==========
TELEGRAM_BOT_TOKEN=your_bot_token_here
AUTHORIZED_USER_IDS=123456789,987654321
ADMIN_USER_IDS=123456789

# ========== STRATEGY ==========
EMA_PERIODS_FAST=5
EMA_PERIODS_MED=10
EMA_PERIODS_SLOW=20
RSI_PERIOD=14
RSI_OVERSOLD_LEVEL=30
RSI_OVERBOUGHT_LEVEL=70
STOCH_K_PERIOD=14
STOCH_D_PERIOD=3
STOCH_SMOOTH_K=3
STOCH_OVERSOLD_LEVEL=20
STOCH_OVERBOUGHT_LEVEL=80
ATR_PERIOD=14
SL_ATR_MULTIPLIER=1.5
DEFAULT_SL_PIPS=25.0
TP_RR_RATIO=1.8
DEFAULT_TP_PIPS=45.0
MAX_SPREAD_PIPS=5.0

# ========== RISK ==========
# Production values (tidak aktif di eval mode)
MAX_TRADES_PER_DAY=5
DAILY_LOSS_PERCENT=3.0
SIGNAL_COOLDOWN_SECONDS=180
MIN_SIGNAL_CONFIDENCE=70.0

# Evaluation mode values (override saat EVALUATION_MODE=true)
DAILY_LOSS_PERCENT_EVAL=5.0
SIGNAL_COOLDOWN_SECONDS_EVAL=60
MIN_SIGNAL_CONFIDENCE_EVAL=60.0

# ========== EVALUATION MODE ==========
EVALUATION_MODE=false
# SET TRUE UNTUK TESTING 24 JAM: unlimited trade, cooldown 60s, loss limit 5%

# ========== DELAY MONITORING ==========
MAX_TICK_DELAY_SECONDS=3.0
ALERT_DELAY_THRESHOLD_SECONDS=5.0

# ========== WEBSOCKET ==========
WS_URL=wss://ws-json.exness.com/realtime
WS_DISCONNECT_ALERT_SECONDS=30
WS_RECONNECT_MAX_ATTEMPTS=10

# ========== LOGGING ==========
LOG_LEVEL=INFO
LOG_FILE=/app/logs/bot.log
LOG_ROTATE_SIZE_MB=10
LOG_BACKUP_COUNT=5

# ========== PATHS ==========
DATABASE_URL=sqlite:///app/data/bot.db
CHART_CACHE_DIR=/app/data/charts
```

---

## **10. DISCLAIMER & LEGAL FRAMEWORK**

```markdown
## ⚠️ PENTING: BACA SEBELUM MENGGUNAKAN

### **1. NO EXECUTION POLICY**
Bot ini adalah **SIGNAL PROVIDER SAJA**. Tidak ada eksekusi trade otomatis. Anda 100% bertanggung jawab eksekusi manual di MT5/MT4.

### **2. EVALUATION MODE WARNING**
**EVALUATION_MODE=true** akan:
- Generate **UNLIMITED SIGNAL** (bypass trade count limit)
- Menggunakan **risk parameter yang lebih longgar** (loss limit 5%, cooldown 60s)
- **HANYA untuk testing 24 jam** untuk analisis win/lose rate
- **JANGAN gunakan mode ini di live trading real money**

### **3. Risiko Data**
Data dari WebSocket Exness bisa delay, disconnect, atau tidak akurat. Bot **SKIP sinyal** jika delay > 3 detik.

### **4. Risiko Modal**
XAUUSD sangat VOLATIL. Modal 100rb-500rb IDR bisa HABIS dalam menit. Hasil evaluasi **tidak menjamin** performa future.

### **5. Tanggung Jawab**
Anda bertanggung jawab penuh atas:
- Setting parameter yang sesuai modal
- Pilihan broker dan eksekusi manual
- Risk management di platform trading Anda

**Gunakan mode evaluasi dengan bijak. Jangan overtrade.**
```

---

## **11. PRE-PRODUCTION CHECKLIST (Eval Mode)**

**Sebelum menjalankan 24 jam evaluasi:**

- [ ] **WebSocket Test:** Delay < 1 detik rata-rata
- [ ] **Database Volume:** Persistent volume `/app/data` sudah di-mount
- [ ] **Environment Variables:** `EVALUATION_MODE=true` dan `MAX_TRADES_PER_DAY=999`
- [ ] **Daily Loss Limit Eval:** Set ke 5% (jangan lebih)
- [ ] **Admin Telegram:** Pastikan dapat alert setiap 6 jam
- [ ] **Log Monitoring:** Pastikan log rotasi aktif (max 10MB)
- [ ] **Health Check:** Endpoint `/health` return JSON valid
- [ ] **Signal Validation:** Test 5-10 sinyal manual, cek entry/SL/TP logic
- [ ] **Chart Generation:** Pastikan chart PNG < 500KB per file
- [ ] **Cooldown Eval:** Set ke 60 detik (jangan 0 untuk hindari spam)

**Setelah 24 jam evaluasi:**
- [ ] Ekspor data dari SQLite ke CSV/Excel
- [ ] Hitung win rate, profit factor, drawdown
- [ ] Analisis sinyal loss: apakah delay tinggi? spread melebar?
- [ ] Tweak parameter confidence, RR ratio, indikator
- [ ] **Matikan eval mode** (`EVALUATION_MODE=false`) sebelum live

---

## **12. NEXT STEPS - IMPLEMENTASI**

**Prioritas:**
1. **File 1:** `ws_manager.py` - WebSocket + delay monitoring
2. **File 2:** `aggregator.py` - OHLCV builder dari tick
3. **File 3:** `strategy.py` - Signal logic + confidence scoring
4. **File 4:** `risk_manager.py` - Risk layer dengan eval mode override
5. **File 5:** `bot.py` - Telegram handlers + commands
6. **File 6:** `main.py` - Main orchestrator + health check Flask endpoint
7. **File 7:** `backtester.py` - CSV replay untuk evaluasi offline

**Testing Flow:**
1. Jalankan di Replit dengan `EVALUATION_MODE=true`
2. Pantau `/status` setiap jam
3. Cek `/performa` setiap 6 jam
4. Setelah 24 jam, matikan bot, export DB, analisis
5. Tweak parameter, ulangi jika perlu
6. Deploy ke Koyeb dengan `EVALUATION_MODE=false`

---

**Prompt ini 100% siap implementasi dengan unlimited trade untuk evaluasi 24 jam, sementara risk layer penting tetap aktif sebagai safety net.**
