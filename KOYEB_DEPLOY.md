# 🚀 Deploy ke Koyeb

Bot sudah siap untuk dideploy ke Koyeb PaaS dengan Docker.

## ✅ Deploy di Koyeb

### Step 1: Buka Koyeb Console
- Masuk ke https://app.koyeb.com
- Klik "Create Service"

### Step 2: Connect GitHub Repository
- Pilih "GitHub"
- Authorize & select `Dzakiart19/Freexausdbot`
- Branch: `main`
- Dockerfile: enabled

### Step 3: Configure Deployment
- **Name**: `xauusd-bot`
- **Build Command**: (empty - Dockerfile)
- **Run Command**: (empty - defined in Dockerfile)
- **Port**: 8080

### Step 4: Add Environment Variables
Klik "Add Secret" dan masukkan:

| Variable | Value |
|----------|-------|
| `TELEGRAM_BOT_TOKEN` | `8083284621:AAGANGmpHZ2op0zbXt-uUb-t9dyUBYi4Ooc` |
| `AUTHORIZED_USER_IDS` | `7390867903` |
| `ADMIN_USER_IDS` | `7390867903` |
| `EVALUATION_MODE` | `true` |
| `LOG_LEVEL` | `INFO` |

### Step 5: Resources
- **CPU**: 500m (0.5 CPU)
- **Memory**: 512Mi
- **Instances**: 1

### Step 6: Deploy
Klik "Deploy" dan tunggu ~2-3 menit hingga aplikasi berjalan.

## ✅ Verify Deployment

Setelah deploy:

1. **Cek Bot di Telegram**
   - Buka Telegram dan cari `@Mt5TradeProBot`
   - Kirim `/start`
   - Bot harus respond dengan menu

2. **Monitor Logs**
   - Di Koyeb dashboard, buka "Logs"
   - Lihat real-time logs bot

3. **Check Health**
   - Kirim command `/health` di Telegram
   - Bot menampilkan system status

## 🔄 Redeploy

Setelah push code ke GitHub:
1. Masuk Koyeb dashboard
2. Pilih service `xauusd-bot`
3. Klik "Redeploy" atau tunggu auto-redeploy (jika enabled)

---

**Repository**: https://github.com/Dzakiart19/Freexausdbot
**Docker Image**: `xauusd-bot:latest`
