import os
import re
import asyncio
import imaplib
import email
import time
import json
import anthropic
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from dotenv import load_dotenv


import platform
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if platform.system() == "Windows" else os.path.expanduser("~/.config/trading")
load_dotenv(os.path.join(BASE_DIR, ".env"))

# Load environment variables
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
    Uses Claude to extract trade details from any signal format.
    Returns a list of trade dicts, or empty list if not a swing trade.
    """
    text = message_text.strip()

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = (
        "You are a trading signal parser. Extract options trade details from this message.\n\n"
        "Rules:\n"
        "- Only extract SWING trades. Day trades, lotto trades, and scalps should be ignored.\n"
        "- If trade_type is ambiguous but expiration is more than 5 days out, treat as swing.\n"
        "- If the message is not an options trade alert, return null.\n"
        "- BTO means Buy To Open - treat as a swing trade entry signal.\n\n"
        "Return ONLY valid JSON in this exact format (no explanation, no markdown):\n"
        "{\n"
        '  "trade_type": "swing",\n'
        '  "ticker": "NVDA",\n'
        '  "strike": 212.5,\n'
        '  "option_type": "CALL",\n'
        '  "expiration": "5/22",\n'
        '  "limit_price": 0.0\n'
        "}\n\n"
        "Or return exactly: null\n\n"
        f"Message:\n{text}"
    )

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            messages=[{"role": "user", "content": prompt}]
        )
        response = message.content[0].text.strip()

        if response.lower() == "null":
            return []

        parsed = json.loads(response)
        if not parsed or parsed.get("trade_type") != "swing":
            return []

        trade = {
            "ticker":      parsed["ticker"].upper().lstrip("$"),
            "strike":      float(parsed["strike"]),
            "option_type": parsed["option_type"].upper(),
            "expiration":  parsed["expiration"],
            "limit_price": float(parsed.get("limit_price") or 0.0),
            "format":      "AI",
            "raw":         text
        }
        return [trade]

    except Exception as e:
        print(f"Signal parse error: {e}")
        return []

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

        # Alpaca option chain data
        chain = get_option_chain_data(
            trade['ticker'], trade['expiration'],
            trade['strike'], trade['option_type']
        )

        result = {
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
            'otm_pct':          round(((trade['strike'] - current_price) / current_price) * 100, 1),
            # Option chain fields — None if unavailable
            'option_symbol':    chain.get('option_symbol') if chain else None,
            'bid':              chain.get('bid') if chain else None,
            'ask':              chain.get('ask') if chain else None,
            'mid':              chain.get('mid') if chain else None,
            'iv':               chain.get('iv') if chain else None,
            'delta':            chain.get('delta') if chain else None,
            'theta':            chain.get('theta') if chain else None,
        }
        return result

    except Exception as e:
        return {**trade, 'verification_error': str(e)}


# ── STAGE 4: DECISION BRIEF ──────────────────────────────────────────────


def generate_brief(verified_trade):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    t      = verified_trade

    # Format option chain line — omit gracefully if data unavailable
    def fmt(val, prefix="", suffix="", fallback="N/A"):
        return f"{prefix}{val}{suffix}" if val is not None else fallback

    chain_lines = (
        f"- Contract: {fmt(t.get('option_symbol'))}\n"
        f"- Bid/Ask: {fmt(t.get('bid'), '$')} / {fmt(t.get('ask'), '$')}  "
        f"Mid: {fmt(t.get('mid'), '$')}\n"
        f"- IV: {fmt(t.get('iv'), suffix='%')}\n"
        f"- Delta: {fmt(t.get('delta'))}  Theta: {fmt(t.get('theta'))}\n"
    )

    prompt = (
        "You are a disciplined options trading analyst. "
        "Analyze this swing trade signal and provide a concise go/no-go recommendation.\n\n"
        f"SIGNAL:\n"
        f"- Ticker: ${t['ticker']}\n"
        f"- Option: {t['strike']} {t['option_type']} exp {t['expiration']}\n"
        f"- Limit Price: ${t['limit_price']}\n\n"
        f"OPTION CHAIN:\n"
        f"{chain_lines}\n"
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
    raw   = message.content[0].text
    clean = re.sub(r"[*_`#]", "", raw)
    return clean


# ── STAGE 5: SMS DELIVERY (Gmail-to-Verizon bridge) ─────────────────────

def send_brief(trade, brief):
    ticker      = trade["ticker"]
    strike      = trade["strike"]
    option_type = trade["option_type"]
    expiration  = trade["expiration"]
    limit_price = trade["limit_price"]

    # Include bid/ask in header if available
    chain_summary = ""
    if trade.get("bid") and trade.get("ask"):
        chain_summary = f"Bid/Ask: ${trade['bid']}/${trade['ask']}"
        if trade.get("iv"):
            chain_summary += f" | IV: {trade['iv']}%"
        chain_summary = f"{chain_summary}\n"

    if limit_price > 0:
        header = f"SWING ALERT: ${ticker}\n{strike} {option_type} {expiration} @ ${limit_price}\n"
        footer = "Reply GO to place order or NO to skip."
    else:
        mid = trade.get("mid")
        mid_str = f"${mid}" if mid else "unavailable"
        header = f"FYI SIGNAL: ${ticker}\n{strike} {option_type} {expiration}\nNo price in signal. Mid: {mid_str}\n"
        footer = "No order will be placed — manual entry only."

    body = (
        f"{header}"
        f"{chain_summary}"
        f"---\n"
        f"{brief}\n"
        f"---\n"
        f"{footer}"
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
    Validates contract exists in Alpaca chain, returns OCC symbol.
    Raises ValueError if contract not found.
    """
    from alpaca.data.historical.option import OptionHistoricalDataClient
    from alpaca.data.requests import OptionChainRequest

    # Build candidate symbol
    exp_month, exp_day = expiration.split('/')
    exp_year = str(datetime.now().year)[2:]
    exp_str  = f"{exp_year}{int(exp_month):02d}{int(exp_day):02d}"
    cp       = "C" if option_type == "CALL" else "P"
    strike_int = int(round(strike * 1000))
    strike_str = f"{strike_int:08d}"
    candidate = f"{ticker}{exp_str}{cp}{strike_str}"

    # Validate against live chain
    try:
        data_client = OptionHistoricalDataClient(
            api_key    = ALPACA_API_KEY,
            secret_key = ALPACA_SECRET_KEY
        )
        exp_date = f"20{exp_year}-{int(exp_month):02d}-{int(exp_day):02d}"
        request  = OptionChainRequest(
            underlying_symbol = ticker,
            expiration_date   = exp_date
        )
        chain = data_client.get_option_chain(request)

        if candidate in chain:
            print(f"Contract validated: {candidate}")
            return candidate
        else:
            raise ValueError(f"Contract {candidate} not found in Alpaca chain for {ticker} {exp_date}")

    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Chain lookup failed for {ticker}: {e}")


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
        os.path.join(BASE_DIR, "telegram_session"),
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

            # Reply monitor and order placement — skip if no limit price
            if trade['limit_price'] <= 0:
                print(f"No limit price for ${trade['ticker']} — FYI brief sent, manual entry only")
            else:
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
