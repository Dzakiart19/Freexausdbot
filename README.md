# **BOT TELEGRAM XAUUSD SCALPING SIGNAL PROVIDER - SPESIFIKASI V2.1 (DELAY MONITORING)**

**Update:** Menambahkan threshold delay, monitoring, dan alerting untuk tick data realtime WebSocket Exness.

---

## **IDENTITAS PROYEK**
**Nama Bot:** `XauScalp Sentinel`  
**Versi:** 2.1.0-WS-DELAY  
**Tujuan:** Signal Provider otomatis 24/7 untuk XAUUSD scalping M1/M5 menggunakan **realtime tick data dari WebSocket broker Exness**  
**Target User:** Trader pemula dengan modal 100rb-500rb IDR (0.01-0.05 lot)  
**Model Risiko:** High-frequency signal dengan strict risk management layer + **delay-aware protection**  
**Mode:** Support Evaluation Mode untuk pengumpulan data 24 jam pertama  
**Disclaimer:** Bot ini **TIDAK mengeksekusi trade**, hanya signal provider

---

## **1. ARSITEKTUR INTI & FILOSOFI**

### **1.1 Design Principles**
- **Zero Execution Guarantee:** Pure signal generator, tidak ada kode eksekusi trade atau integrasi MetaTrader API.
- **Real-Time First:** Semua sinyal harus berasal dari **tick data realtime** (bid/ask) dari WebSocket Exness.
- **No External API Keys:** Tidak perlu API key berbayar. Semua data dari WebSocket broker.
- **Tick-to-OHLCV Aggregation:** Build M1 dan M5 candle secara real-time dari tick data.
- **Auto-Reconnect:** WebSocket harus reconnect otomatis dengan exponential backoff saat disconnect.
- **Delay-Aware:** **SKIP sinyal** jika tick data delay > 3 detik untuk proteksi modal.
- **Signal-First Architecture:** Semua komponen bekerja secara *asynchronous* dan *non-blocking*.

### **1.2 High-Level Flow**
```
[Exness WebSocket Tick Feed] → [Delay Validator] → [OHLCV Aggregator] → [Multi-Timeframe Analysis Engine] 
→ [Signal Validator] → [Risk Manager] → [Telegram Dispatcher] 
→ [Position Monitor] → [Result Reporter]
```

---

## **2. KONEKSI WEBSOCKET EXNESS - SPESIFIKASI TEKNIS**

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
  "timestamp": 1700044800  // Unix epoch seconds
}
```

### **2.3 WebSocket Manager (`ws_manager.py`)**

**Responsibilitas:**
- Connect ke `wss://ws-json.exness.com/realtime`
- Kirim payload subscribe `{"type":"subscribe","pairs":["XAUUSD"]}`
- Terima message, parse JSON, ekstrak `bid`, `ask`, `timestamp`
- Update **in-memory price cache** (`current_bid`, `current_ask`, `last_tick_time`)
- Hitung **delay** setiap tick: `delay = time.time() - timestamp`
- Trigger **OHLCV aggregator** hanya jika delay acceptable

**Reconnect Logic:**
- Jika disconnect, tunggu `2^n * 5 detik` (max 60 detik) sebelum reconnect
- Kirim alert ke admin Telegram jika disconnect > `WS_DISCONNECT_ALERT_SECONDS` (default 30 detik)
- Max reconnect attempts = `WS_RECONNECT_MAX_ATTEMPTS` (default 10)
- Set status `WS_DEGRADED` jika reconnect gagal

**Error Handling:**
- Jika receive message invalid/broken JSON → log warning, continue
- Jika timestamp tidak valid → gunakan `time.time()` sebagai fallback
- Jika bid/ask = 0 atau None → skip tick, tunggu berikutnya
- **Jika delay > `MAX_TICK_DELAY_SECONDS` → SKIP processing, log warning**

### **2.4 OHLCV Aggregator (`aggregator.py`)**

**Responsibilitas:**
- Build candle M1 dan M5 secara real-time dari tick data
- Simpan **500 bars terakhir** di in-memory deque (RAM efisien)
- Struktur data:
  ```python
  m1_candle = {
      "open": first_bid_of_minute,
      "high": max(bid_during_minute),
      "low": min(bid_during_minute),
      "close": last_bid_of_minute,
      "volume": count_of_ticks_during_minute,
      "timestamp": "2025-11-15T12:30:00"
  }
  ```

**Logika Pembentukan Candle:**
- **M1 Candle:** Reset setiap menit (detik = 00)
- **M5 Candle:** Reset setiap 5 menit (menit kelipatan 5, detik = 00)
- Gunakan **bid price** sebagai harga utama untuk konsistensi
- Volume = jumlah tick dalam periode

**Persistensi:**
- Simpan ke SQLite setiap candle selesai (async write, tidak blocking)
- Table: `ohlcv_cache(timeframe, timestamp, open, high, low, close, volume)`

---

## **3. STRATEGI TRADING - ADAPTASI UNTUK TICK DATA**

### **3.1 Perubahan Dasar**
- **Data Source:** Semua indikator dihitung dari **OHLCV hasil aggregasi**, bukan API external
- **Spread Calculation:** `current_spread = ask - bid` (pips = spread * 100)
- **Signal Validity:** Hanya generate sinyal jika **WebSocket connected** dan **candle M1/M5 sudah closed**
- **Delay Protection:** **SKIP sinyal** jika `get_current_delay() > MAX_TICK_DELAY_SECONDS`

### **3.2 Konfigurasi Strategy (Tetap Sama)**
```env
# EMA
EMA_PERIODS_FAST=5
EMA_PERIODS_MED=10
EMA_PERIODS_SLOW=20

# RSI
RSI_PERIOD=14
RSI_OVERSOLD_LEVEL=30
RSI_OVERBOUGHT_LEVEL=70

# Stochastic
STOCH_K_PERIOD=14
STOCH_D_PERIOD=3
STOCH_SMOOTH_K=3
STOCH_OVERSOLD_LEVEL=20
STOCH_OVERBOUGHT_LEVEL=80

# ATR & Risk
ATR_PERIOD=14
SL_ATR_MULTIPLIER=1.5
DEFAULT_SL_PIPS=25.0
TP_RR_RATIO=1.8
DEFAULT_TP_PIPS=45.0
MAX_SPREAD_PIPS=5.0

# Volume Filter
VOLUME_THRESHOLD_MULTIPLIER=1.5
VOLUME_LOOKBACK_PERIOD=20
MIN_SIGNAL_CONFIDENCE=70.0
```

### **3.3 Entry Price Logic**
- **Entry Price:** Gunakan **ask** untuk BUY, **bid** untuk SELL (sesuai market execution)
- **SL/TP Calculation:** Berdasarkan entry price + ATR(M5) atau pips default
- **Timestamp Signal:** Waktu candle close (UTC)

---

## **4. RISK & ACCOUNT PROTECTION LAYER**

### **4.1 Virtual Account State**
```python
virtual_balance = 1000000  # Representasi modal 500rb IDR
risk_per_trade = virtual_balance * (RISK_PER_TRADE_PERCENT / 100)
daily_loss_limit = virtual_balance * (DAILY_LOSS_PERCENT / 100)
```

### **4.2 Risk Manager Rules**
- **Daily Drawdown:** Jika loss kumulatif > `DAILY_LOSS_PERCENT%` (default 3%), bot pause
- **Max Concurrent Trades:** `MAX_CONCURRENT_TRADES=1`
- **Signal Cooldown:** `SIGNAL_COOLDOWN_SECONDS=180` per arah (BUY/SELL terpisah)
- **Max Trades Per Day:** `MAX_TRADES_PER_DAY=5` (production), override di evaluation mode
- **Delay Protection:** **SKIP sinyal** jika `get_current_delay() > MAX_TICK_DELAY_SECONDS`

### **4.3 EVALUATION MODE (Untuk Testing 24 Jam)**
```env
EVALUATION_MODE=true  # Aktifkan mode evaluasi
MAX_TRADES_PER_DAY=100  # Override limit trade count, tapi risk layer lain tetap aktif
DAILY_LOSS_PERCENT=5.0  # Failsafe tetap ada, tapi longgar
```

**Logika di Kode:**
```python
EVALUATION_MODE = os.getenv('EVALUATION_MODE', 'false').lower() == 'true'
MAX_TRADES_PER_DAY = int(os.getenv('MAX_TRADES_PER_DAY', 5))

def can_generate_signal():
    # DELAY CHECK - SKIP if data stale
    if ws_manager.get_current_delay() > float(os.getenv('MAX_TICK_DELAY_SECONDS', 3.0)):
        logger.warning(f"Signal paused: delay={ws_manager.get_current_delay():.2f}s")
        return False
    
    if EVALUATION_MODE:
        return check_other_risk_rules()  # Skip trade count limit
    return trades_today < MAX_TRADES_PER_DAY
```

---

## **5. TELEGRAM BOT INTERFACE - PERINTAH & OTORISASI**

### **5.1 Perintah Dasar**
- `/start`: Sambutan + otorisasi check
- `/help`: List semua command
- `/status`: Lihat status bot, WebSocket health, trade count hari ini, **current delay**
- `/monitor XAUUSD`: Subscribe sinyal
- `/stopmonitor XAUUSD`: Unsubscribe
- `/riwayat [n]`: Lihat trade history terakhir

### **5.2 Perintah Admin**
- `/performa [period]`: Statistik performa
- `/settings`: Ubah parameter via inline keyboard
- `/pausebot` & `/resumebot`: Control bot state
- `/forceclose <signal_id>`: Emergency close position
- `/health`: Detail WebSocket latency, uptime, reconnect count, **delay metrics**

### **5.3 Format Pesan Sinyal**
```
🚀 XAUUSD SCALPING SIGNAL

📈 Tipe: BUY
⏰ Timeframe: M1/M5
💰 Entry: 2035.20 (ask)
🎯 TP: 2037.20 (+45 pips)
🛑 SL: 2032.70 (-25 pips)
📊 Confidence: 75%
📏 Spread: 3.2 pips
⏱️ Signal Time: 2025-11-15 12:30:00 UTC / 19:30 WIB
⏱️ Feed Delay: 0.15s (✅ fresh)

⚠️ Risk: 0.5% per trade
```

---

## **6. WEBSOCKET HEALTH MONITORING & ALERTING**

### **6.1 WebSocket Metrics**
- **Connection Status:** Connected / Disconnected / Reconnecting
- **Last Tick Received:** Timestamp terakhir tick valid
- **Latency:** Selisih `time.time() - tick_timestamp` (harus < 2 detik)
- **Reconnect Count:** Counter reconnect hari ini
- **Tick Rate:** Ticks per second (ideal: 1-5 tick/detik untuk XAUUSD)

### **6.2 Telegram Alerts**
- **WARNING:** WebSocket disconnect > 30 detik
- **CRITICAL:** Tidak ada tick baru > 2 menit (market mungkin closed atau WS down)
- **HIGH DELAY:** `delay > ALERT_DELAY_THRESHOLD_SECONDS` (default 5 detik)
- **INFO:** Reconnect berhasil

### **6.3 Health Check Endpoint (`/health`)**
```python
@app.route('/health')
def health_check():
    return jsonify({
        "status": "healthy" if all_ok else "degraded",
        "websocket": {
            "status": ws_manager.connection_status,
            "last_tick_time": ws_manager.last_tick_time,
            "delay_seconds": ws_manager.get_current_delay(),
            "reconnect_count_today": ws_manager.reconnect_count,
            "tick_rate_per_sec": ws_manager.get_tick_rate()
        },
        "active_signals": active_signals_count,
        "trades_today": trades_today,
        "evaluation_mode": EVALUATION_MODE
    }), 200 if all_ok else 503
```

---

## **7. PERSISTENSI & DATABASE**

### **7.1 SQLite Schema (Simplified)**
```python
# Tabel: ohlcv_cache
- timeframe (STRING: M1, M5)
- timestamp_utc (DATETIME)
- open, high, low, close (FLOAT)
- volume (INT)
- PRIMARY KEY (timeframe, timestamp_utc)

# Tabel: trades (sama seperti V1)

# Tabel: bot_state
- key (STRING: ws_reconnect_count, last_tick_time, daily_loss)
- value (JSON)
- updated_at (TIMESTAMP)

# Tabel: ws_health_log (baru)
- timestamp (DATETIME)
- delay_ms (INT)
- status (ENUM: normal, warning, critical)
- message (TEXT)
```

### **7.2 Write Strategy**
- Write candle ke DB setiap **menit (M1)** dan **5 menit (M5)** secara **asynchronous**
- Jangan block main thread saat write DB
- Write health log setiap 5 detik untuk monitoring delay

---

## **8. LOGGING & OBSERVABILITY**

### **8.1 Log Events**
```python
[2025-11-15 12:30:00] [INFO] [ws_manager] Connected to Exness WebSocket
[2025-11-15 12:30:01] [INFO] [aggregator] M1 candle closed: O=2035.10 H=2035.50 L=2035.05 C=2035.45 V=125
[2025-11-15 12:30:02] [INFO] [strategy] Signal BUY generated, confidence=75%
[2025-11-15 12:30:03] [INFO] [bot] Signal sent to Telegram: signal_id=abc123
[2025-11-15 12:30:05] [WARNING] [ws_manager] Tick delay 3.5s > 3.0s, skipping...
[2025-11-15 12:30:10] [CRITICAL] [ws_manager] High delay detected: 5.2s, alerting admin
[2025-11-15 12:30:15] [INFO] [ws_manager] Delay back to normal: 0.8s
```

### **8.2 Log File**
- Path: `/app/logs/bot.log`
- Rotating: Max 10MB, backup 5 files
- Level: INFO ke stdout, WARNING/ERROR ke file + Telegram admin

---

## **9. DEPLOYMENT - KOYEB & REPLIT**

### **9.1 Environment Variables (FINAL)**
```bash
# ========== CORE ==========
TELEGRAM_BOT_TOKEN=your_bot_token_here
AUTHORIZED_USER_IDS=123456789
ADMIN_USER_IDS=123456789

# ========== STRATEGY ==========
EMA_PERIODS_FAST=5
EMA_PERIODS_MED=10
EMA_PERIODS_SLOW=20
RSI_PERIOD=14
RSI_OVERSOLD_LEVEL=30
STOCH_K_PERIOD=14
STOCH_D_PERIOD=3
ATR_PERIOD=14
SL_ATR_MULTIPLIER=1.5
TP_RR_RATIO=1.8
MAX_SPREAD_PIPS=5.0
MIN_SIGNAL_CONFIDENCE=70.0

# ========== RISK ==========
SIGNAL_COOLDOWN_SECONDS=180
MAX_TRADES_PER_DAY=5
DAILY_LOSS_PERCENT=3.0
RISK_PER_TRADE_PERCENT=0.5
MAX_CONCURRENT_TRADES=1

# ========== EVALUATION MODE ==========
EVALUATION_MODE=false
# Set true untuk testing 24 jam pertama

# ========== DELAY MONITORING (BARU) ==========
MAX_TICK_DELAY_SECONDS=3.0
ALERT_DELAY_THRESHOLD_SECONDS=5.0

# ========== WEBSOCKET ==========
WS_URL=wss://ws-json.exness.com/realtime
WS_DISCONNECT_ALERT_SECONDS=30
WS_RECONNECT_MAX_ATTEMPTS=10

# ========== LOGGING ==========
LOG_LEVEL=INFO
LOG_FILE=/app/logs/bot.log
```

### **9.2 Dockerfile (Tidak Berubah)**
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    gcc \
    libgl1-mesa-glx \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/data /app/logs

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import requests; sys.exit(0 if requests.get('http://localhost:8080/health').json()['websocket']['status'] == 'connected' else 1)"

CMD ["python", "-u", "main.py"]
```

---

## **10. DISCLAIMER & LEGAL FRAMEWORK**

```markdown
## ⚠️ PENTING: BACA SEBELUM MENGGUNAKAN

### **1. NO EXECUTION POLICY**
Bot ini adalah **SIGNAL PROVIDER SAJA**. Tidak ada eksekusi trade otomatis.

### **2. Sumber Data**
Data harga berasal dari **WebSocket Exness** (public feed). Tidak ada jaminan akurasi, delay, atau kelengkapan data. Bot akan **SKIP sinyal** jika delay > 3 detik.

### **3. Risiko Trading**
XAUUSD sangat **VOLATIL**. Modal bisa HABIS dalam menit. Sinyal bukan financial advice.

### **4. Evaluation Mode Warning**
Saat `EVALUATION_MODE=true`, bot generate banyak sinyal untuk testing. **Jangan gunakan di live environment.**

### **5. Tanggung Jawab**
Anda 100% bertanggung jawab untuk eksekusi manual, risk management, dan hasil trading.
```

---

## **11. PRE-PRODUCTION CHECKLIST**

**Sebelum Deploy ke Koyeb:**

- [ ] **WebSocket Connect Test:** Pastikan connect ke `wss://ws-json.exness.com/realtime`
- [ ] **WebSocket Delay Test:** Jalankan 1 jam, pastikan **avg delay < 1 detik**
- [ ] **Stale Tick Test:** Simulasikan delay 5 detik, pastikan **tick di-skip dan sinyal pause**
- [ ] **Alert Test:** Pastikan Telegram alert kirim jika **delay > 5 detik**
- [ ] **Signal Test:** Generate 10+ sinyal di evaluation mode, cek logika entry/SL/TP
- [ ] **Risk Test:** Simulasikan 3 loss streak, pastikan cooldown dan daily loss limit aktif
- [ ] **Telegram Test:** Semua command reply dengan cepat (< 2 detik)
- [ ] **Memory Test:** Monitor RAM usage, harus **< 200MB** untuk 500 bars di memory
- [ ] **Log Test:** Pastikan log rotating berfungsi, tidak memenuhi disk
- [ ] **Health Check Test:** `curl http://localhost:8080/health` return JSON valid

---

## **12. NEXT STEPS - MULAI CODING**

1. **File pertama:** `ws_manager.py` - Bangun WebSocket client dengan reconnect & delay validation
2. **File kedua:** `aggregator.py` - Buat OHLCV builder dari tick data
3. **File ketiga:** `strategy.py` - Implementasi logika sinyal dengan delay check
4. **File keempat:** `bot.py` - Telegram command handlers
5. **File kelima:** `main.py` - Orchestrate semua services

**Fokus pada stabilitas WebSocket dan delay monitoring dulu.** Jika data feed tidak stabil, semua sinyal akan gagal.

---

**Prompt ini 100% siap implementasi dengan delay monitoring integrated.** Tidak perlu rewrite dari nol.
