# Trading Pipeline — Change Log
**Endoge LLC / Vexara IQ Inc.  •  MS-01 Fletcher Hub  •  Started: May 19, 2026**
Owner: Jerry Tice  •  Pipeline: `~/trading/pipeline.py` on MS-01  •  Credentials: `~/.config/trading/.env`

---

## Session Change Log

| Date | Session | Area | Changes / Notes | Author |
|------|---------|------|-----------------|--------|
| 2026-05-19 | 1 | Initial Setup | Project context established. Pipeline state documented (Stages 1–5 + reply monitor). Changelog created. | Jerry / Claude |
| 2026-05-19 | 2 | Pipeline / Infra | Cleaned .env (removed duplicate Alpaca block, removed IBKR lines, relabeled # Gmail section). Built and deployed Stage 6 Alpaca order placement module. Tested OCC symbol builder. Confirmed Alpaca paper account connection ($200k buying power, status ACTIVE). pipeline.py rewritten: startup test code removed, IBKR vars removed, reply monitor wired into main handler, Stage 6 fully integrated. alpaca-py installed on MS-01. | Jerry / Claude |
| 2026-05-21 | 3 | Pipeline / Infra | **SMS fix:** Stripped markdown characters (`*_\`#`) from Claude API output before SMS send (`32a01a8`). **Format B:** Added PUT support to Dane parser — dynamic opt_type from regex capture (`f885280`). **Format C:** Added Brian Axelrod parser (TICKER STRIKE CALL/PUT MM/DD + "entry per contract" price) (`f885280`). **Stage 3:** Added `get_option_chain_data()` — fetches bid/ask/mid/IV/delta/theta via Alpaca `OptionSnapshotRequest`; fails gracefully if contract unavailable. **Stage 4 prompt:** Added OPTION CHAIN section feeding greeks/IV to Claude. **Stage 5 SMS:** Bid/ask and IV now shown in SMS header when available. **NUC15:** Ollama installed as systemd service, bound to all interfaces (`0.0.0.0:11434`); Nemotron-Cascade-2 (24GB) pull initiated. MS-01 → NUC15 connectivity confirmed via Tailscale. | Jerry / Claude |

---

## Next Actions / Backlog

| Pri | Action Item | Owner / Machine | Status |
|-----|-------------|-----------------|--------|
| 1 | ~~Add ALPACA_API_KEY, ALPACA_SECRET_KEY, ALPACA_ENDPOINT to ~/.config/trading/.env~~ | Jerry → MS-01 | ✅ Done |
| 2 | ~~Build Alpaca order placement module (Stage 6) in pipeline.py~~ | Jerry / Claude | ✅ Done |
| 3 | ~~Evaluate Alpaca market data for option chain (bid/ask, IV, delta, theta) in Stage 3~~ | Jerry / Claude | ✅ Done — OI not available in snapshot API |
| 4 | ~~Clean up startup test code in pipeline.py~~ | Jerry / Claude | ✅ Done |
| 5 | ~~Fix markdown asterisks in SMS brief output~~ | Jerry / Claude | ✅ Done |
| 6 | ~~Add PUT support to Format B (Dane) parser~~ | Jerry / Claude | ✅ Done |
| 7 | ~~Add Format C parser for Brian Axelrod~~ | Jerry / Claude | ✅ Done |
| 8 | ~~Wrap pipeline.py in systemd service on MS-01~~ | Jerry / MS-01 | ✅ Done (prior session) |
| 9 | Alpaca option chain — OI field | Jerry / Claude | Pending — not in snapshot API; evaluate alternatives |
| 10 | Cascade-2 smoke test on NUC15 | Jerry / NUC15 | Pending — pull in progress |
| 11 | Nemotron 70B pull on NUC15 | Jerry / NUC15 | Pending — after Cascade-2 validated |
| 12 | Open WebUI for David | Jerry / NUC15 | Pending — after Cascade-2 running |
| 13 | First end-to-end paper trade test (wait for live TradeAlgo signal) | Jerry | Pending |
| 14 | Attorney: Delaware corporate + startup IP (83(b) election clock not started) | Jerry | Pending |
| 15 | CPA: Endoge/Vexara financials, retroactive Jan 1 2026 | Jerry | Pending |
| 16 | Geekom A9 Max integration planning (arriving summer 2026) | Jerry | Future |

---

## Lab Stack Quick Reference

| Host | OS / Hardware | Role | Key Details |
|------|--------------|------|-------------|
| MS-01 (Fletcher Hub) | Ubuntu 24.04 | Orchestration & pipeline host | 192.168.10.10 local \| 100.68.9.125 Tailscale |
| NUC15 | Ubuntu, 80GB RAM | Ollama inference host | 100.97.109.36 Tailscale \| Nemotron-Cascade-2 pulling \| CPU-only |
| Desktop | Windows, RTX 5060 Ti | GPU workloads | Heavy compute / local model training |
| Geekom A9 Max | Coming summer 2026, 128GB RAM | Future heavy inference node | Not yet deployed |
| Mac Mini | macOS | Secondary access | Connected via Tailscale |
| Raspberry Pis | Raspberry Pi OS | Edge / monitoring | Various edge tasks |

---

*SEPARATION RULE: Lab stack (Endoge/Vexara) is completely isolated from Synergetics/MW360/Synovate work.*
