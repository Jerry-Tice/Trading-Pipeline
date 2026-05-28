# Trading Pipeline — Changelog
**Project:** Trading Pipeline — Endoge Lab
**Repo:** Jerry-Tice/Trading-Pipeline
**Last Updated:** 2026-05-27 (Session 5 Part 2)

---

## Session Log

| Date | Session | Area | Changes / Notes | Author |
|------|---------|------|-----------------|--------|
| 2026-05-18 | 1 | Infrastructure | Alpaca account created. API key, secret, and paper endpoint obtained. Credentials stored in `~/.config/trading/.env` on MS-01. Paper trading confirmed default. IBKR abandoned — 2FA/Gateway friction with TWS/IBC/Xvfb. | Jerry |
| 2026-05-18 | 1 | Architecture | Pipeline architecture defined: TradeAlgo Telegram signal → Claude parser → yfinance verification → Claude decision brief → SMS (Verizon gateway) → GO/NO reply monitor → Alpaca order placement. | Jerry / Claude |
| 2026-05-19 | 2 | Build | Alpaca execution module built replacing IBKR. `build_option_symbol()` function written (OCC format: TICKER+YYMMDD+C/P+8-digit strike). `place_order()` wired to paper-api.alpaca.markets. SMS confirmation and error handlers added. | Jerry / Claude |
| 2026-05-19 | 2 | Build | Signal parser built using Claude API (claude-sonnet-4-6). Filters swing trades only — ignores day trades, scalps, lotto trades. Returns structured trade dict. | Jerry / Claude |
| 2026-05-19 | 2 | Build | `verify_trade()` built using yfinance: pulls 60-day history, computes MA20, MA50, RSI, volume vs average, earnings date check, OTM%. Alpaca option chain data appended (bid, ask, mid, IV, delta, theta). | Jerry / Claude |
| 2026-05-19 | 2 | Build | `generate_brief()` built — Claude produces GO/NO-GO/CONDITIONAL GO verdict with risk, technicals, catalyst, and action summary. | Jerry / Claude |
| 2026-05-19 | 2 | Build | `send_brief()` built — Gmail-to-Verizon SMS gateway (8282319520@vtext.com). 1600 char limit enforced. | Jerry / Claude |
| 2026-05-19 | 2 | Build | `wait_for_reply()` built — polls Gmail inbox for GO/NO reply from Verizon number. 30-minute timeout. Snapshots inbox before waiting to ignore stale messages. | Jerry / Claude |
| 2026-05-21 | 3 | Infrastructure | systemd service configured: `/etc/systemd/system/trading-pipeline.service`. Service enabled for auto-start on boot. Pipeline confirmed running headlessly on MS-01 (Ubuntu, Tailscale IP 100.68.9.125). | Jerry / Claude |
| 2026-05-21 | 3 | Infrastructure | Telegram session authenticated on MS-01. Session file stored at `~/.config/trading/telegram_session`. Monitoring TradeAlgoAlertsChannel confirmed active. | Jerry / Claude |
| 2026-05-26 | 4 | Testing | Lab offline — storm/UPS took MS-01, Mac Mini M2, and G9-1 down. Shifted to Windows laptop (HP Envy, C:\Users\gttic\trading-test) as fallback environment. | Jerry |
| 2026-05-26 | 4 | Testing | Python 3.14.5 installed on laptop. alpaca-py installed to system Python. Alpaca paper account auth validated: status ACTIVE, buying power $200K, Level 3 options confirmed. | Jerry / Claude |
| 2026-05-26 | 4 | Testing | Test order placed: SPY260529C00575000 @ $1.00 limit, qty 1, status ACCEPTED. Confirmed in Alpaca dashboard. Order cancelled after validation. | Jerry / Claude |
| 2026-05-26 | 4 | Strategy | Signal source pivot discussed. TradeAlgo has not delivered swing-aligned signals since pipeline completion (day trades, scalps, oil futures only). Evaluated Simpler Trading, Option Alpha, Unusual Whales, Benzinga. Self-directed signal model proposed: Simpler Scanner → manual SMS to Google Voice → pipeline execution. | Jerry / Claude |
| 2026-05-27 | 5 | Signal | First real swing trade signal received from MrConfluence via TradeAlgo Telegram: NVDA $225 C 07/17, entry $7.80 limit, Buy to Open. Signal flagged RISKY by analyst. Stop: $207.50. Targets: $218/$224.25/$229/$238. | Jerry |
| 2026-05-27 | 5 | Testing | Contract validation: queried Alpaca options chain for NVDA expiration 2026-07-17. 194 contracts returned. Target contract NVDA260717C00225000 confirmed listed. | Jerry / Claude |
| 2026-05-27 | 5 | Execution | Paper order placed from laptop: NVDA260717C00225000 @ $7.80 limit, qty 1 (=$780 exposure, within $500-$1K parameter). Order ID: 140e3d0b-e3e3-4252-b2fb-648f8d393446. Status: PENDING_NEW → filled. | Jerry / Claude |
| 2026-05-27 | 5 | Execution | Order confirmed filled in Alpaca dashboard. Position: NVDA260717C00225000, price $7.50, market value $750, P/L -$30 (paper). Daily change -$30.02. | Jerry |
| 2026-05-27 | 5 | Infrastructure | Lab restored by Caleb — MikroTik router, TP-Link switch, and MS-01 back online after storm/UPS reset. | Caleb / Jerry |
| 2026-05-27 | 5 | Infrastructure | MS-01 trading-pipeline.service confirmed auto-started on boot: active (running), PID 1198, 187MB memory. No manual intervention required. | Jerry |
| 2026-05-27 | 5 | Code | Cross-platform path fix applied to pipeline.py. `load_dotenv` and `telegram_session` paths now use OS detection: Windows uses `os.path.dirname(os.path.abspath(__file__))`, Linux uses `~/.config/trading`. `import platform` added. `BASE_DIR` variable introduced. | Jerry / Claude |
| 2026-05-27 | 5 | Code | Updated pipeline.py pushed to GitHub (commit 530027d): "Cross-platform path handling for Windows and Linux". 1 file changed, 6 insertions, 3 deletions. | Jerry |
| 2026-05-27 | 5 | Infrastructure | MS-01 pulled updated code from GitHub (fast-forward merge). Service restarted: active (running), PID 1698. Both environments now in sync on cross-platform codebase. Laptop pipeline retired — MS-01 is authoritative monitor. | Jerry / Claude |

---

## Open Backlog

| # | Item | Priority | Status |
|---|------|----------|--------|
| 1 | Fix `build_option_symbol()` — live chain lookup before order submission | High | ✅ Done |
| 2 | Wire Google Voice SMS intake as self-directed signal source channel | High | Open |
| 3 | Build Telegram signal parser test harness | Medium | ✅ Done |
| 4 | Evaluate Simpler Trading scanner as primary self-directed signal source | Medium | Research |
| 5 | Monitor NVDA260717C00225000 position — expiry July 17, 2026. Stop: $207.50 underlying | Medium | Active |
| 6 | Restore Mac Mini M2 and G9-1 after UPS reset | Low | Pending |

---

## Lab Stack

| Device | Role | Status | Notes |
|--------|------|--------|-------|
| MS-01 (fletcher-hub) | Primary pipeline host | ONLINE | Ubuntu, Tailscale 100.68.9.125, systemd service active |
| Mac Mini M2 | Nemo/OpenClaw host | TBD | Needs post-storm status check |
| G9-1 | Lab workstation | TBD | Needs post-storm status check |
| MikroTik RB5009 | Router / dual-WAN | ONLINE | Restored by Caleb 2026-05-27 |
| TP-Link Switch | Gigabit switch | ONLINE | Restored by Caleb 2026-05-27 |
| Windows Laptop (HP Envy) | Fallback environment | STANDBY | Pipeline retired, alpaca-py + dependencies installed |

---

## Key Decisions

| Decision | Rationale | Date |
|----------|-----------|------|
| Alpaca over IBKR | Pure API key auth, no 2FA/Gateway friction, paper trading default, Level 3 options | 2026-05-18 |
| Paper trading first | Validate pipeline before live capital | 2026-05-18 |
| IBKR retained for manual positions | Not part of automated pipeline | 2026-05-18 |
| MS-01 as primary host | Ubuntu, headless, always-on via Tailscale, systemd managed | 2026-05-21 |
| Self-directed signal model | TradeAlgo signals not aligned with swing parameters; retain human judgment on entry | 2026-05-26 |
| Cross-platform codebase | Single pipeline.py with OS detection — no separate Windows/Linux versions | 2026-05-27 |

---

*IP Boundary: Personal trading automation — Endoge territory only. No Synergetics data, client information, or code involved.*
| 2026-05-27 | 5b | Code | `build_option_symbol()` refactored — now queries live Alpaca options chain before building OCC symbol. Raises `ValueError` if contract not found. Prevents blind symbol submission that caused 422 errors in testing. Commit: fbbe5d4. | Jerry / Claude |
| 2026-05-27 | 5b | Code | `alpaca.data.historical.option.OptionHistoricalDataClient` integrated into `build_option_symbol()`. Chain lookup uses `OptionChainRequest` with `underlying_symbol` and `expiration_date`. Validates candidate symbol exists in returned chain before proceeding. | Jerry / Claude |
| 2026-05-27 | 5b | Testing | Parser test harness built: `test_parser.py`. Five test cases: MrConfluence NVDA real signal, day trade (ignored), scalp (ignored), non-trade message (ignored), BTO swing call. Initial run: 4/5 passed. | Jerry / Claude |
| 2026-05-27 | 5b | Bug Fix | `parse_signal()` fix: Claude API returning JSON wrapped in markdown code fences. `json.loads()` failing on fence characters. Fixed with `re.sub()` to strip fences before parsing. Commit: c91f9ef. | Jerry / Claude |
| 2026-05-27 | 5b | Bug Fix | `parse_signal()` fix: emoji characters in MrConfluence alerts causing empty API response. Fixed with `re.sub(r'[^\x00-\x7F]+', ' ', message_text)` to strip non-ASCII before sending to Claude. | Jerry / Claude |
| 2026-05-27 | 5b | Bug Fix | `parse_signal()` fix: `max_tokens` increased from 200 to 400 to prevent JSON response truncation. | Jerry / Claude |
| 2026-05-27 | 5b | Testing | Parser test harness rerun after fixes: 5/5 passed. NVDA signal correctly parsed (ticker: NVDA, strike: 225.0, type: CALL, expiry: 7/17, limit: 7.80). All filter cases correctly ignored. | Jerry / Claude |
| 2026-05-27 | 5b | Infrastructure | MS-01 git conflict resolved with `git pull origin main --rebase`. Clean fast-forward push after rebase. | Jerry / Claude |
| 2026-05-27 | 5b | Infrastructure | Service restarted with all fixes live: active (running), PID 2261. Pipeline fully validated end to end — parsing, chain validation, and order execution all confirmed. | Jerry / Claude |
