# Claude Token Tracker

Persistent token usage and budget tracker for the Anthropic Claude API.
Shows remaining budget at the start and end of every work session.

## Features
- 💰 **Daily & monthly budget tracking** — persistent across sessions
- 🌅 **Start-of-session report** — see exactly how much budget is left before you start
- 🌙 **End-of-session report** — summary of what you spent, what's left
- 📊 **Full report** — last 7 days + monthly breakdown
- 🤖 **Auto model routing** — picks cheapest model that fits the task
- 🗜️ **Auto history compression** — summarises old messages to save tokens
- 🔴 **Budget warnings** — alerts at 75% and 90% usage

## Setup

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your_api_key_here
```

Or edit `tracker.py` and set `API_KEY = "your_key"` directly.

## Set Your Budget

Edit these two lines in `tracker.py`:
```python
MONTHLY_BUDGET = 20.0   # $ per month
DAILY_BUDGET   = 2.0    # $ per day soft limit
```

## Usage

```bash
# Start a chat session (shows budget at start + end)
python tracker.py

# View full usage report without starting a chat
python tracker.py --report

# Reset monthly tracking (start of new month)
python tracker.py --reset
```

## In-Chat Commands

| Command | What it does |
|---------|-------------|
| `report` | Show full usage report |
| `reset chat` | Clear conversation history (saves tokens) |
| `quit` | End session + show end-of-session report |

## Example Start-of-Session Output

```
══════════════════════════════════════════════════
  🌅 START OF SESSION — 2026-04-03
══════════════════════════════════════════════════

  📅 TODAY  (2026-04-03)
     Used:      $0.0842 / $2.00
     Remaining: $1.9158
     🟢 [████░░░░░░░░░░░░░░░░] 4.2%

  📆 THIS MONTH  (2026-04)
     Used:      $3.2400 / $20.00
     Remaining: $16.7600
     Calls:     48
     🟢 [███░░░░░░░░░░░░░░░░░] 16.2%

  💡 You can spend ~$0.6523/day for the rest of the month
```

## Example End-of-Session Output

```
══════════════════════════════════════════════════
  🌙 END OF SESSION — 2026-04-03
══════════════════════════════════════════════════

  ── THIS SESSION ──────────────────────────
     Calls made:     12
     Input tokens:   8,432
     Output tokens:  5,210
     Session cost:   $0.1042

  ── TODAY TOTAL ───────────────────────────
     Spent today:    $0.1884 / $2.00

  ── MONTH REMAINING ───────────────────────
     Remaining:      $16.5716
     Days left:      27
     Daily budget:   ~$0.6138/day

  ✅ Session saved. See you next time!
```

## Data Storage

Usage is saved in `usage_data.json` in the same folder — never lost between sessions.

## Author
Harsh Vardhan Singh Chauhan — [github.com/ehansih](https://github.com/ehansih)
