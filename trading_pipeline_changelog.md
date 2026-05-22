# Trading Pipeline — Change Brief
**Date:** May 21, 2026
**Session:** Fletcher Hub / MS-01
**Author:** Jerry Tice | Endoge LLC

---

## Changes Committed This Session

### 1. SMS Markdown Fix
**Commit:** `32a01a8` — *Fix markdown asterisks in SMS brief output*

Claude API responses were including markdown formatting characters (`*`, `_`, `` ` ``, `#`) that rendered as literal symbols in Verizon SMS.

**Fix:** Added a strip pass in `generate_brief()` before returning the brief:
```python
raw   = message.content[0].text
clean = re.sub(r"[*_`#]", "", raw)
return clean
```

---

### 2. Format B — PUT Support Added
**Commit:** `f885280` — *Add PUT support to Format B, add Format C parser for Brian Axelrod*

Format B (Dane Glisek) parser was CALL-only. Updated regex to capture both CALL and PUT, with dynamic `opt_type` assignment.

**Before:**
```python
r'\$([A-Z]+)\s+(\d{1,2}/\d{2})\s+([\d.]+)\s*C(?:all)?'
'option_type': 'CALL'  # hardcoded
```

**After:**
```python
r'\$([A-Z]+)\s+(\d{1,2}/\d{2})\s+([\d.]+)\s*(C(?:all)?|P(?:ut)?)'
opt_type = 'PUT' if match[3].upper().startswith('P') else 'CALL'
```

**Note:** Eight months of Dane signals reviewed — only one PUT found, and it was a daytrade (filtered by swing trade gate). PUT support added for completeness.

---

### 3. Format C — Brian Axelrod Parser Added
**Commit:** `f885280` — *Add PUT support to Format B, add Format C parser for Brian Axelrod*

Brian Axelrod's signal format is structurally distinct from Format A (MrConfluence) and Format B (Dane). Added Format C parser.

**Brian's format:**
```
SWING TRADE
RIVN 14.5 PUT 5/15
TINY POSITION 1%
.28 entry per contract
...
BM
```

**Parser:**
```python
# Format C: Brian Axelrod - TICKER STRIKE CALL/PUT MM/DD
format_c = re.findall(
    r'^([A-Z]+)\s+([\d.]+)\s+(CALL|PUT)\s+(\d{1,2}/\d{2})',
    text, re.IGNORECASE | re.MULTILINE
)
# Price extracted from: ".28 entry per contract"
price_match = re.search(r'([\d.]+)\s+entry per contract', text, re.IGNORECASE)
```

---

### 4. Alpaca Option Chain Data — Stage 3
**Commit:** *(latest)* — *Add Alpaca option chain data to Stage 3 — bid/ask/IV/delta/theta in brief and SMS*

Stage 3 previously relied solely on yfinance for equity-level technicals. Added a new `get_option_chain_data()` function that fetches live option contract data from Alpaca's market data API for the specific contract in the signal.

**New function:** `get_option_chain_data(ticker, expiration, strike, option_type)`
- Builds OCC symbol from trade fields
- Hits `OptionHistoricalDataClient` → `OptionSnapshotRequest`
- Returns: `bid`, `ask`, `mid`, `iv`, `delta`, `theta`
- Fails gracefully — returns `None` if contract not found or API unavailable

**New fields added to verified trade dict:**
| Field | Source |
|---|---|
| `option_symbol` | Built from trade fields |
| `bid` | Alpaca latest quote |
| `ask` | Alpaca latest quote |
| `mid` | Calculated (bid+ask)/2 |
| `iv` | Alpaca implied volatility |
| `delta` | Alpaca greeks |
| `theta` | Alpaca greeks |

**Stage 4 prompt updated:** OPTION CHAIN section added above TECHNICAL DATA, feeding bid/ask/mid/IV/delta/theta to Claude for brief generation.

**Stage 5 SMS updated:** Bid/ask and IV added to SMS header line when available:
```
SWING ALERT: $AAPL
200 CALL 6/20 @ $2.50
Bid/Ask: $2.45/$2.55 | IV: 34.2%
---
VERDICT: GO
...
```

---

## Lab Infrastructure — NUC15 Setup

### Ollama Installed
- Installed via `curl -fsSL https://ollama.com/install.sh | sh`
- Running as systemd service, survives reboots
- CPU-only mode (expected — no discrete GPU on NUC15)

### Bound to All Interfaces
Configured `/etc/systemd/system/ollama.service.d/override.conf`:
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0"
```
Ollama now listens on `*:11434` — reachable from MS-01 and David's machine via Tailscale.

**MS-01 → NUC15 connectivity confirmed:**
```bash
curl http://100.97.109.36:11434
# Ollama is running
```

### Nemotron-Cascade-2 Pull In Progress
- 24GB model, pulling via `nohup` (survives SSH disconnect)
- ETA ~3 hours from session end
- Log: `~/ollama-pull.log` on NUC15

**Check status:**
```bash
ssh jtice@100.97.109.36 "tail ~/ollama-pull.log"
```

---

## Pending / Next Session

| Item | Status |
|---|---|
| Cascade-2 smoke test | Waiting on pull to complete |
| Nemotron 70B backup pull | After Cascade-2 validated |
| First live paper trade test | Waiting on real TradeAlgo signal |
| Open WebUI for David | After Cascade-2 running |
| Alpaca option chain — OI field | Not available in snapshot API; evaluate alternatives |

---

## Commit Log (This Session)

| Hash | Message |
|---|---|
| `ae6910a` | Add README |
| `32a01a8` | Fix markdown asterisks in SMS brief output |
| `f885280` | Add PUT support to Format B, add Format C parser for Brian Axelrod |
| *(latest)* | Add Alpaca option chain data to Stage 3 — bid/ask/IV/delta/theta in brief and SMS |
