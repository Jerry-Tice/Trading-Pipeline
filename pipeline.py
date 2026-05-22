import os
import re
import asyncio
import imaplib
import email
import time
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv

# Load environment variables
load_dotenv(os.path.expanduser("~/.config/trading/.env"))

ANTHROPIC_API_KEY    = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_API_ID      = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH    = os.getenv("TELEGRAM_API_HASH")
GMAIL_ADDRESS        = os.getenv("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD   = os.getenv("GMAIL_APP_PASSWORD")
ALPACA_API_KEY       = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY    = os.getenv("ALPACA_SECRET_KEY")
ALPACA_ENDPOINT      = os.getenv("ALPACA_ENDPOINT", "https://paper-api.alpaca.markets/v2")

SMS_GATEWAY          = "8282319520@vtext.com"
TRADEALGO_CHANNEL    = "TradeAlgoAlertsChannel"

print("Environment loaded successfully")

# ── STAGE 2: SIGNAL PARSER ──────────────────────────────────────────────

def parse_signal(message_text):
    """
    Returns a list of trade dicts if message is a swing trade alert.
    Returns empty list if message should be ignored.
    """
    text = message_text.strip()

    if not re.search(r'swing trade', text, re.IGNORECASE):
        return []

    trades = []

    # Format A: MrConfluence - $TICKER $STRIKE C/P MM/DD @ PRICE
    format_a = re.findall(
        r'\$([A-Z]+)\s+\$?([\d.]+)\s+([CP])\s+(\d{1,2}/\d{2})\s+@\s+([\d.]+)',
        text, re.IGNORECASE
    )
    for match in format_a:
        trades.append({
            'ticker': match[0].upper(),
            'strike': float(match[1]),
            'option_type': 'CALL' if match[2].upper() == 'C' else 'PUT',
            'expiration': match[3],
            'limit_price': float(match[4]),
            'format': 'A',
            'raw': text
        })

    # Format B: Dane - $TICKER MM/DD STRIKECall or $TICKER MM/DD STRIKE C
    format_b = re.findall(
        r'\$([A-Z]+)\s+(\d{1,2}/\d{2})\s+([\d.]+)\s*C(?:all)?',
        text, re.IGNORECASE
    )
    for match in format_b:
        fill_match  = re.search(r'Fill Price:\s*([\d.]+)', text, re.IGNORECASE)
        limit       = float(fill_match.group(1)) if fill_match else 0.0
        stop_match  = re.search(r'Stop Loss[^:]*:\s*([^\n]+)', text, re.IGNORECASE)
        stop        = stop_match.group(1).strip() if stop_match else None
        targets     = re.findall(r'(?:1st|2nd|Final)\s+Target:\s*([\d.]+)', text, re.IGNORECASE)

        trades.append({
            'ticker':      match[0].upper(),
            'strike':      float(match[2]),
            'option_type': 'CALL',
            'expiration':  match[1],
            'limit_price': limit,
            'stop_loss':   stop,
            'targets':     targets,
            'format':      'B',
            'raw':         text
        })

    return trades


# ── STAGE 3: VERIFICATION LAYER ─────────────────────────────────────────

import yfinance as yf

def verify_trade(trade):
    ticker = trade['ticker']
    print(f"\nVerifying {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        hist  = stock.history(period="60d")
        if hist.empty:
            return {**trade, 'verification_error': 'No price data'}

        current_price = hist['Close'].iloc[-1]
        ma50          = hist['Close'].rolling(window=50).mean().iloc[-1]
        ma20          = hist['Close'].rolling(window=20).mean().iloc[-1]

        delta = hist['Close'].diff()
        gain  = delta.clip(lower=0).rolling(window=14).mean()
        loss  = -delta.clip(upper=0).rolling(window=14).mean()
        rsi   = (100 - (100 / (1 + gain / loss))).iloc[-1]

        avg_volume  = hist['Volume'].rolling(window=20).mean().iloc[-1]
        last_volume = hist['Volume'].iloc[-1]

        try:
            calendar      = stock.calendar
            next_earnings = calendar.get('Earnings Date', [None])[0] if calendar else None
        except Exception:
            next_earnings = None

        exp_month, exp_day = trade['expiration'].split('/')
        exp_date = datetime(datetime.now().year, int(exp_month), int(exp_day))

        earnings_before_exp = False
        if next_earnings:
            try:
                ne_dt               = datetime(next_earnings.year, next_earnings.month, next_earnings.day)
                earnings_before_exp = ne_dt <= exp_date
            except Exception:
                earnings_before_exp = None

        return {
            **trade,
            'current_price':    round(float(current_price), 2),
            'ma20':             round(float(ma20), 2),
            'ma50':             round(float(ma50), 2),
            'rsi':              round(float(rsi), 1),
            'above_ma20':       bool(current_price > ma20),
            'above_ma50':       bool(current_price > ma50),
            'avg_volume_20d':   int(avg_volume),
            'last_volume':      int(last_volume),
            'volume_above_avg': bool(last_volume > avg_volume),
            'next_earnings':    str(next_earnings) if next_earnings else 'Unknown',
            'earnings_before_exp': earnings_before_exp,
            'otm_pct':          round(((trade['strike'] - current_price) / current_price) * 100, 1)
        }
    except Exception as e:
        return {**trade, 'verification_error': str(e)}


# ── STAGE 4: DECISION BRIEF ──────────────────────────────────────────────

import anthropic

def generate_brief(verified_trade):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    t      = verified_trade
    prompt = (
        "You are a disciplined options trading analyst. "
        "Analyze this swing trade signal and provide a concise go/no-go recommendation.\n\n"
        f"SIGNAL:\n"
        f"- Ticker: ${t['ticker']}\n"
        f"- Option: {t['strike']} {t['option_type']} exp {t['expiration']}\n"
        f"- Limit Price: ${t['limit_price']}\n\n"
        f"TECHNICAL DATA:\n"
        f"- Current Price: ${t.get('current_price', 'N/A')}\n"
        f"- OTM: {t.get('otm_pct', 'N/A')}%\n"
        f"- RSI: {t.get('rsi', 'N/A')}\n"
        f"- Above 20-day MA: {t.get('above_ma20', 'N/A')}\n"
        f"- Above 50-day MA: {t.get('above_ma50', 'N/A')}\n"
        f"- Volume vs Average: {'Above' if t.get('volume_above_avg') else 'Below'} average\n\n"
        f"RISK CHECK:\n"
        f"- Next Earnings: {t.get('next_earnings', 'Unknown')}\n"
        f"- Earnings before expiration: {t.get('earnings_before_exp', 'Unknown')}\n\n"
        "Respond in this exact format:\n"
        "VERDICT: [GO / NO-GO / CONDITIONAL GO]\n"
        "RISK: [1-2 sentence risk summary]\n"
        "TECHNICALS: [1-2 sentence technical summary]\n"
        "CATALYST: [1 sentence on earnings/news risk]\n"
        "ACTION: [1 sentence on what to watch before placing]"
    )
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text


# ── STAGE 5: SMS DELIVERY (Gmail-to-Verizon bridge) ─────────────────────

def send_brief(trade, brief):
    ticker      = trade["ticker"]
    strike      = trade["strike"]
    option_type = trade["option_type"]
    expiration  = trade["expiration"]
    limit_price = trade["limit_price"]

    body = (
        f"SWING ALERT: ${ticker}\n"
        f"{strike} {option_type} {expiration} @ ${limit_price}\n"
        f"---\n"
        f"{brief}\n"
        f"---\n"
        f"Reply GO to place order or NO to skip."
    )

    if len(body) > 1600:
        body = body[:1597] + "..."

    msg            = MIMEText(body)
    msg["From"]    = GMAIL_ADDRESS
    msg["To"]      = SMS_GATEWAY
    msg["Subject"] = ""

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_ADDRESS, SMS_GATEWAY, msg.as_string())
        print(f"Brief sent via SMS for ${ticker}")


# ── REPLY MONITOR ────────────────────────────────────────────────────────

def wait_for_reply(ticker, timeout_minutes=30):
    """
    Polls Gmail inbox for GO/NO reply.
    Returns True if GO, False if NO or timeout.
    """
    print(f"Waiting for GO/NO reply for ${ticker}...")
    deadline = time.time() + (timeout_minutes * 60)
    seen_uids = set()

    # Snapshot inbox before waiting to ignore old messages
    with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
        mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        mail.select("inbox")
        _, existing = mail.search(None, "ALL")
        for uid in existing[0].split():
            seen_uids.add(uid)

    while time.time() < deadline:
        try:
            with imaplib.IMAP4_SSL("imap.gmail.com") as mail:
                mail.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
                mail.select("inbox")
                _, messages = mail.search(None, "ALL")

                for uid in messages[0].split():
                    if uid in seen_uids:
                        continue
                    seen_uids.add(uid)

                    _, data = mail.fetch(uid, "(RFC822)")
                    msg    = email.message_from_bytes(data[0][1])
                    sender = msg.get("From", "")

                    if "vtext.com" not in sender and "8282319520" not in sender:
                        continue

                    body = ""
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_type() == "text/plain":
                                body = part.get_payload(decode=True).decode().strip().upper()
                                break
                    else:
                        payload = msg.get_payload()
                        if isinstance(payload, list):
                            for part in payload:
                                try:
                                    body = part.get_payload(decode=True).decode().strip().upper()
                                    break
                                except Exception:
                                    pass
                        else:
                            body = str(payload).strip().upper()

                    print(f"Reply received: {body}")

                    if "GO" in body and "NO" not in body:
                        print(f"GO confirmed for ${ticker}")
                        return True
                    elif "NO" in body:
                        print(f"NO-GO for ${ticker}")
                        return False

        except Exception as e:
            print(f"Mail check error: {e}")

        time.sleep(30)

    print(f"Timeout — no reply for ${ticker} within {timeout_minutes} minutes")
    return False


# ── STAGE 6: ORDER PLACEMENT (Alpaca) ───────────────────────────────────

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, AssetClass

def build_option_symbol(ticker, expiration, strike, option_type):
    """
    Builds OCC option symbol: TICKER + YYMMDD + C/P + 8-digit strike.
    Example: AAPL250620C00150000
    """
    exp_month, exp_day = expiration.split('/')
    exp_year = str(datetime.now().year)[2:]  # 2-digit year
    exp_str  = f"{exp_year}{int(exp_month):02d}{int(exp_day):02d}"

    cp       = "C" if option_type == "CALL" else "P"
    # Strike in OCC format: multiply by 1000, zero-pad to 8 digits
    strike_int = int(round(strike * 1000))
    strike_str = f"{strike_int:08d}"

    return f"{ticker}{exp_str}{cp}{strike_str}"


def place_order(trade):
    """
    Places a limit order for 1 options contract via Alpaca.
    Returns order object on success, None on failure.
    """
    ticker      = trade['ticker']
    strike      = trade['strike']
    option_type = trade['option_type']
    expiration  = trade['expiration']
    limit_price = trade['limit_price']

    # Alpaca options require limit price > 0
    if limit_price <= 0:
        print(f"Cannot place order for ${ticker}: limit price is 0 or missing")
        return None

    try:
        # Strip /v2 if present — alpaca-py adds versioning internally
        base_url = ALPACA_ENDPOINT.replace("/v2", "")

        client = TradingClient(
            api_key    = ALPACA_API_KEY,
            secret_key = ALPACA_SECRET_KEY,
            paper      = True,
            url_override = base_url
        )

        symbol = build_option_symbol(ticker, expiration, strike, option_type)
        print(f"Placing order: {symbol} @ ${limit_price} limit (1 contract)")

        order_request = LimitOrderRequest(
            symbol       = symbol,
            qty          = 1,
            side         = OrderSide.BUY,
            type         = "limit",
            time_in_force = TimeInForce.DAY,
            limit_price  = limit_price
        )

        order = client.submit_order(order_request)
        print(f"Order placed: ID {order.id} | Status: {order.status}")
        send_order_confirmation(trade, order)
        return order

    except Exception as e:
        print(f"Order placement failed for ${ticker}: {e}")
        send_order_error(trade, str(e))
        return None


def send_order_confirmation(trade, order):
    """Sends SMS confirmation after order is placed."""
    body = (
        f"ORDER PLACED: ${trade['ticker']}\n"
        f"{trade['strike']} {trade['option_type']} {trade['expiration']}\n"
        f"Limit: ${trade['limit_price']} | Qty: 1\n"
        f"Order ID: {order.id}\n"
        f"Status: {order.status}"
    )
    try:
        msg            = MIMEText(body)
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = SMS_GATEWAY
        msg["Subject"] = ""
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, SMS_GATEWAY, msg.as_string())
        print(f"Order confirmation sent for ${trade['ticker']}")
    except Exception as e:
        print(f"Failed to send order confirmation: {e}")


def send_order_error(trade, error_msg):
    """Sends SMS alert if order placement fails."""
    body = (
        f"ORDER FAILED: ${trade['ticker']}\n"
        f"{trade['strike']} {trade['option_type']} {trade['expiration']}\n"
        f"Error: {error_msg}"
    )
    try:
        msg            = MIMEText(body)
        msg["From"]    = GMAIL_ADDRESS
        msg["To"]      = SMS_GATEWAY
        msg["Subject"] = ""
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_ADDRESS, SMS_GATEWAY, msg.as_string())
        print(f"Order error notification sent for ${trade['ticker']}")
    except Exception as e:
        print(f"Failed to send order error notification: {e}")


# ── STAGE 1: TELEGRAM MONITOR ───────────────────────────────────────────

from telethon import TelegramClient, events

async def main():
    client = TelegramClient(
        os.path.expanduser("~/.config/trading/telegram_session"),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH
    )

    await client.start()
    print("Telegram connected. Monitoring TradeAlgo channel...")

    @client.on(events.NewMessage(chats=TRADEALGO_CHANNEL))
    async def handler(event):
        message = event.message.message
        print(f"\nNew message: {message[:100]}...")

        # Stage 2: Parse
        trades = parse_signal(message)
        if not trades:
            print("Not a swing trade signal — ignored")
            return

        print(f"Swing trade signal — {len(trades)} trade(s) detected")

        for trade in trades:
            print(f"\nProcessing ${trade['ticker']}...")

            # Stage 3: Verify
            verified = verify_trade(trade)
            if "verification_error" in verified:
                print(f"Verification error: {verified['verification_error']}")
                continue

            # Stage 4: Generate brief
            brief = generate_brief(verified)
            print(f"Brief generated for ${trade['ticker']}")

            # Stage 5: Send SMS
            send_brief(trade, brief)

            # Reply monitor: wait for GO/NO
            go = await asyncio.get_event_loop().run_in_executor(
                None, wait_for_reply, trade['ticker']
            )

            # Stage 6: Place order
            if go:
                print(f"GO received — placing order for ${trade['ticker']}")
                await asyncio.get_event_loop().run_in_executor(
                    None, place_order, trade
                )
            else:
                print(f"NO-GO or timeout for ${trade['ticker']} — no order placed")

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
