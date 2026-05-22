# Trading Pipeline

Automated swing trade signal processor for TradeAlgo Alerts Channel. Monitors Telegram for swing trade alerts, verifies signals independently, delivers a GO/NO-GO decision brief via SMS, and places limit orders on Alpaca paper trading upon approval.

**Owner:** Jerry Tice | Endoge LLC  
**Host:** MS-01 (Ubuntu 24.04, Fletcher Hub)

---

## Architecture

```
TradeAlgo Telegram Channel
        ↓
Stage 1: Telegram Monitor (Telethon)
        ↓
Stage 2: Signal Parser
        ↓ swing trades + equity options only
Stage 3: Verification Layer (yfinance)
        ↓ technicals, earnings, OTM%
Stage 4: Decision Brief (Claude API)
        ↓ GO/NO-GO analysis
Stage 5: SMS Delivery (Gmail → Verizon)
        ↓ brief sent to phone
   Reply Monitor (Gmail IMAP)
        ↓ polls for GO/NO reply
Stage 6: Order Placement (Alpaca)
        ↓ limit order, 1 contract, paper account
```

---

## Signal Filtering

Captures messages containing `swing trade` (case insensitive) with a valid equity options structure. All other message types are discarded:

- ❌ Day trades — PDT rule avoidance
- ❌ Futures (Silver, Crude Oil, Micro Gold)
- ❌ Crypto
- ❌ Scalps
- ❌ Morning briefings, exit updates, commentary

**Format A (MrConfluence):**
```
SWING TRADE ALERT
$C $129 C 06/26 @ 3.10
$XLY $120 C 06/26 @ 1.90
```

**Format B (Dane Glisek):**
```
Swing Trade Alert (SMALL SIZE)
$RKT 5/29 14C
Fill Price: .46
Stop Loss: daily close below 13.3
1st Target: 14.5
2nd Target: 15
Final Target: 15.87
```

---

## Verification Layer

For each parsed signal, the pipeline pulls:

- **Current price** vs strike (OTM%)
- **RSI** (14-day)
- **MA20 and MA50** — price above/below
- **Volume** vs 20-day average
- **Next earnings date** — flags if before expiration
- **Verdict** — GO / NO-GO / CONDITIONAL GO via Claude API

---

## Decision Brief (SMS Format)

```
SWING ALERT: $C
129.0 CALL 06/26 @ $3.1
---
VERDICT: NO-GO
RISK: Option is 5.4% OTM requiring significant move before expiration.
TECHNICALS: RSI 34 oversold but below 20-day MA shows near-term weakness.
CATALYST: No earnings before expiration.
ACTION: Wait for price to reclaim 20-day MA before entering.
```

Reply **GO** to place the order. Reply **NO** or no reply within 30 minutes to stand down.

---

## Order Placement

On GO confirmation, the pipeline places a **limit order** on Alpaca:
- 1 contract
- Limit price from the signal
- Paper trading account (default)
- Confirmation SMS sent with order ID and status

---

## Prerequisites

- Python 3.12+
- Ubuntu 24.04 (MS-01)
- Alpaca account (paper trading enabled)
- Telegram API credentials (my.telegram.org)
- Gmail account with App Password (trading.gttice@gmail.com)
- Verizon cell for SMS delivery via vtext.com
- Anthropic API key

---

## Python Dependencies

```bash
pip3 install telethon anthropic yfinance alpaca-py \
             python-dotenv twilio --break-system-packages
```

---

## Configuration

Credentials stored at `~/.config/trading/.env` (chmod 600):

```env
# Anthropic
ANTHROPIC_API_KEY=

# Telegram
TELEGRAM_API_ID=
TELEGRAM_API_HASH=

# Gmail (trading account)
GMAIL_ADDRESS=trading.gttice@gmail.com
GMAIL_APP_PASSWORD=

# Alpaca
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
ALPACA_ENDPOINT=https://paper-api.alpaca.markets

# Twilio (dormant - A2P 10DLC pending)
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
TWILIO_FROM_NUMBER=+18286726421
TWILIO_TO_NUMBER=+18282319520

# IBKR (manual trading only - not used by pipeline)
IBKR_PORT=4002
IBKR_ACCOUNT=DU6906629
```

---

## Running the Pipeline

**Manual:**
```bash
cd ~/trading
python3 pipeline.py
```

First run will prompt for Telegram phone verification (one-time).

**As a systemd service (production):**
```bash
sudo systemctl start trading-pipeline
sudo systemctl status trading-pipeline
sudo journalctl -u trading-pipeline -f
```

The service starts automatically on boot and restarts on failure.

---

## Systemd Service

Located at `/etc/systemd/system/trading-pipeline.service`

---

## Notes

- **Twilio** is configured but blocked by A2P 10DLC registration. SMS delivery uses Gmail-to-Verizon bridge (vtext.com) instead.
- **IBKR/IBC** is installed at `~/ibc` and `~/ibgateway` but abandoned in favor of Alpaca for automated execution. IBKR retained for manual trading.
- Pipeline runs 24/7 — only swing trade signals during market hours will produce actionable alerts.
- Paper trading by default. Live trading requires updating ALPACA_ENDPOINT and confirming options permissions on live account.

---

## Project Structure

```
~/trading/
├── pipeline.py          # Main pipeline script
└── .gitignore           # Excludes .env and session files
```

Telegram session stored at `~/.config/trading/telegram_session`.
