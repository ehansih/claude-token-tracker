"""
Claude Token & Budget Tracker
==============================
- Tracks token usage and cost across sessions persistently
- Shows remaining budget at start and end of each work session
- Auto-compresses conversation history to save tokens
- Routes to cheapest model automatically

Usage:
    python tracker.py          # start chat session
    python tracker.py --report # show today's + monthly report
    python tracker.py --reset  # reset monthly budget tracking
"""

import anthropic
import json
import os
import sys
from datetime import datetime, date

# ── CONFIG — edit these ──────────────────────────────────────────────────────
API_KEY          = os.environ.get("ANTHROPIC_API_KEY", "your_api_key_here")
MONTHLY_BUDGET   = 20.0          # $ per month — change to your plan
DAILY_BUDGET     = 2.0           # $ per day soft limit
DATA_FILE        = "usage_data.json"  # persistent storage
SUMMARY_THRESHOLD = 3000         # compress history after this many tokens
MAX_OUTPUT_TOKENS = 1024

MODELS = {
    "cheap":    "claude-haiku-4-5-20251001",
    "normal":   "claude-sonnet-4-6",
    "powerful": "claude-opus-4-6",
}

COSTS = {
    "claude-haiku-4-5-20251001": {"in": 0.80,  "out": 4.00},
    "claude-sonnet-4-6":         {"in": 3.00,  "out": 15.00},
    "claude-opus-4-6":           {"in": 15.00, "out": 75.00},
}

# ── PERSISTENT STORAGE ───────────────────────────────────────────────────────
def load_data() -> dict:
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {
        "monthly": {},   # { "2026-04": { "cost": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0 } }
        "daily":   {},   # { "2026-04-03": { "cost": 0.0, ... } }
        "sessions": []   # list of session summaries
    }

def save_data(data: dict):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def record_usage(data: dict, model: str, input_tokens: int, output_tokens: int):
    cost_per_m = COSTS[model]
    cost = (input_tokens / 1_000_000 * cost_per_m["in"] +
            output_tokens / 1_000_000 * cost_per_m["out"])

    today     = str(date.today())            # "2026-04-03"
    this_month = today[:7]                   # "2026-04"

    # Daily
    if today not in data["daily"]:
        data["daily"][today] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
    data["daily"][today]["cost"]          += cost
    data["daily"][today]["input_tokens"]  += input_tokens
    data["daily"][today]["output_tokens"] += output_tokens
    data["daily"][today]["calls"]         += 1

    # Monthly
    if this_month not in data["monthly"]:
        data["monthly"][this_month] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
    data["monthly"][this_month]["cost"]          += cost
    data["monthly"][this_month]["input_tokens"]  += input_tokens
    data["monthly"][this_month]["output_tokens"] += output_tokens
    data["monthly"][this_month]["calls"]         += 1

    save_data(data)
    return cost

# ── REPORTS ──────────────────────────────────────────────────────────────────
def print_banner(title: str):
    print("\n" + "═" * 50)
    print(f"  {title}")
    print("═" * 50)

def start_of_day_report(data: dict):
    today      = str(date.today())
    this_month = today[:7]

    daily_used   = data["daily"].get(today, {}).get("cost", 0.0)
    monthly_used = data["monthly"].get(this_month, {}).get("cost", 0.0)
    monthly_calls = data["monthly"].get(this_month, {}).get("calls", 0)

    daily_left   = DAILY_BUDGET   - daily_used
    monthly_left = MONTHLY_BUDGET - monthly_used

    daily_pct   = (daily_used   / DAILY_BUDGET)   * 100
    monthly_pct = (monthly_used / MONTHLY_BUDGET) * 100

    def bar(pct):
        filled = int(pct / 5)
        empty  = 20 - filled
        color  = "🟢" if pct < 50 else "🟡" if pct < 80 else "🔴"
        return f"{color} [{'█' * filled}{'░' * empty}] {pct:.1f}%"

    print_banner(f"🌅 START OF SESSION — {today}")
    print(f"\n  📅 TODAY  ({today})")
    print(f"     Used:      ${daily_used:.4f} / ${DAILY_BUDGET:.2f}")
    print(f"     Remaining: ${daily_left:.4f}")
    print(f"     {bar(daily_pct)}")

    print(f"\n  📆 THIS MONTH  ({this_month})")
    print(f"     Used:      ${monthly_used:.4f} / ${MONTHLY_BUDGET:.2f}")
    print(f"     Remaining: ${monthly_left:.4f}")
    print(f"     Calls:     {monthly_calls}")
    print(f"     {bar(monthly_pct)}")

    # Days left in month
    today_dt   = date.today()
    import calendar
    last_day   = calendar.monthrange(today_dt.year, today_dt.month)[1]
    days_left  = last_day - today_dt.day + 1
    daily_allowance = monthly_left / days_left if days_left > 0 else 0

    print(f"\n  💡 You can spend ~${daily_allowance:.4f}/day for the rest of the month")
    print("═" * 50)

    if monthly_pct >= 90:
        print("  🔴  CRITICAL: Over 90% of monthly budget used!")
    elif monthly_pct >= 75:
        print("  🟡  WARNING:  Over 75% of monthly budget used.")
    elif daily_pct >= 90:
        print("  🟡  Today's daily budget nearly exhausted.")

def end_of_day_report(data: dict, session_tokens_in: int, session_tokens_out: int, session_cost: float, session_calls: int):
    today      = str(date.today())
    this_month = today[:7]

    daily_used   = data["daily"].get(today, {}).get("cost", 0.0)
    monthly_used = data["monthly"].get(this_month, {}).get("cost", 0.0)
    monthly_left = MONTHLY_BUDGET - monthly_used

    import calendar
    today_dt  = date.today()
    last_day  = calendar.monthrange(today_dt.year, today_dt.month)[1]
    days_left = last_day - today_dt.day

    print_banner(f"🌙 END OF SESSION — {today}")
    print(f"\n  ── THIS SESSION ──────────────────────────")
    print(f"     Calls made:     {session_calls}")
    print(f"     Input tokens:   {session_tokens_in:,}")
    print(f"     Output tokens:  {session_tokens_out:,}")
    print(f"     Session cost:   ${session_cost:.4f}")

    print(f"\n  ── TODAY TOTAL ───────────────────────────")
    print(f"     Spent today:    ${daily_used:.4f} / ${DAILY_BUDGET:.2f}")

    print(f"\n  ── MONTH REMAINING ───────────────────────")
    print(f"     Remaining:      ${monthly_left:.4f}")
    print(f"     Days left:      {days_left}")
    if days_left > 0:
        print(f"     Daily budget:   ~${monthly_left / days_left:.4f}/day")

    # Save session summary
    data["sessions"].append({
        "date":          today,
        "time":          datetime.now().strftime("%H:%M"),
        "calls":         session_calls,
        "input_tokens":  session_tokens_in,
        "output_tokens": session_tokens_out,
        "cost":          round(session_cost, 6)
    })
    save_data(data)
    print("═" * 50)
    print("  ✅ Session saved. See you next time!\n")

def full_report(data: dict):
    today      = str(date.today())
    this_month = today[:7]

    print_banner("📊 FULL USAGE REPORT")

    # Last 7 days
    print("\n  ── LAST 7 DAYS ───────────────────────────")
    print(f"  {'Date':<12} {'Calls':>6} {'Input':>8} {'Output':>8} {'Cost':>8}")
    print(f"  {'─'*12} {'─'*6} {'─'*8} {'─'*8} {'─'*8}")
    for i in range(6, -1, -1):
        from datetime import timedelta
        d = str(date.today() - timedelta(days=i))
        if d in data["daily"]:
            day = data["daily"][d]
            print(f"  {d:<12} {day['calls']:>6} {day['input_tokens']:>8,} {day['output_tokens']:>8,} ${day['cost']:>7.4f}")
        else:
            print(f"  {d:<12} {'─':>6} {'─':>8} {'─':>8} {'─':>8}")

    # Monthly
    print(f"\n  ── MONTHLY BREAKDOWN ─────────────────────")
    for month, m in sorted(data["monthly"].items(), reverse=True)[:3]:
        print(f"  {month}:  ${m['cost']:.4f} used  ({m['calls']} calls)  "
              f"{'← current' if month == this_month else ''}")

    monthly_used = data["monthly"].get(this_month, {}).get("cost", 0.0)
    print(f"\n  Monthly budget:   ${MONTHLY_BUDGET:.2f}")
    print(f"  Used this month:  ${monthly_used:.4f}")
    print(f"  Remaining:        ${MONTHLY_BUDGET - monthly_used:.4f}")
    print("═" * 50)

# ── TOKEN UTILITIES ──────────────────────────────────────────────────────────
def count_tokens(text: str) -> int:
    return len(text) // 4

def count_history_tokens(history: list) -> int:
    return sum(count_tokens(m["content"]) for m in history)

def preflight_count_tokens(client, model: str, messages: list, system: str = "") -> dict:
    """
    Call /v1/messages/count_tokens before sending a message.
    Returns {"input_tokens": N, "predicted_cost": $X} or falls back to estimate
    if the API call fails (e.g. invalid key in tests).
    Free to call — no tokens consumed, no rate-limit impact on message quota.
    """
    try:
        kwargs = {"model": model, "messages": messages}
        if system:
            kwargs["system"] = system
        result = client.messages.count_tokens(**kwargs)
        input_tokens = result.input_tokens
    except Exception:
        # Fallback: rough estimate (4 chars ≈ 1 token)
        input_tokens = count_history_tokens(messages)

    cost_per_m = COSTS.get(model, {"in": 3.00, "out": 15.00})
    predicted_cost = input_tokens / 1_000_000 * cost_per_m["in"]
    return {"input_tokens": input_tokens, "predicted_cost": predicted_cost}

def summarise_history(history: list, client) -> list:
    if len(history) < 4:
        return history
    old, recent = history[:-2], history[-2:]
    text = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in old)
    resp = client.messages.create(
        model=MODELS["cheap"],
        max_tokens=300,
        messages=[{"role": "user", "content": f"Summarise in 5 bullet points:\n\n{text}"}]
    )
    summary = resp.content[0].text
    compressed = [
        {"role": "user",      "content": f"[Previous summary]:\n{summary}"},
        {"role": "assistant", "content": "Got it, I have the context."}
    ] + recent
    print(f"\n  ✅ History compressed ({len(old)} messages → 1 summary)\n")
    return compressed

def pick_model(message: str) -> str:
    import re
    msg = message.lower()
    simple = ["what is", "define", "hi", "hello", "thanks", "yes", "no", "ok", "sure"]
    hard   = ["architecture", "audit", "design system", "research", "analyse", "compare"]
    is_simple = any(re.search(r'\b' + re.escape(k) + r'\b', msg) for k in simple)
    if is_simple and len(message) < 80:
        return MODELS["cheap"]
    if any(k in msg for k in hard):
        return MODELS["powerful"]
    return MODELS["normal"]

# ── MAIN CHAT LOOP ───────────────────────────────────────────────────────────
def main():
    client = anthropic.Anthropic(api_key=API_KEY)
    data   = load_data()

    # Handle CLI flags
    if "--report" in sys.argv:
        full_report(data)
        return
    if "--reset" in sys.argv:
        this_month = str(date.today())[:7]
        data["monthly"][this_month] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
        save_data(data)
        print("✅ Monthly tracking reset.")
        return

    # Session tracking
    session_cost   = 0.0
    session_in     = 0
    session_out    = 0
    session_calls  = 0
    history        = []

    # Start of session report
    start_of_day_report(data)

    print("\n  💬 Chat started! Commands: 'report' | 'reset chat' | 'quit'")
    print("  ─" * 25)

    while True:
        try:
            user_input = input("\n  You: ").strip()
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input:
            continue

        if user_input.lower() == "quit":
            break

        if user_input.lower() == "report":
            full_report(data)
            continue

        if user_input.lower() == "reset chat":
            history = []
            print("  🔄 Chat history cleared — tokens saved!")
            continue

        # Check monthly budget
        this_month   = str(date.today())[:7]
        monthly_used = data["monthly"].get(this_month, {}).get("cost", 0.0)
        if monthly_used >= MONTHLY_BUDGET:
            print("  ⛔ Monthly budget exhausted. Use --reset to reset.")
            break

        # Build messages + pick model
        history.append({"role": "user", "content": user_input})
        model = pick_model(user_input)
        system_prompt = "You are a helpful assistant for Harsh Vardhan Singh Chauhan — telecom security expert."

        # ── PREFLIGHT: count tokens before sending (free API call) ───────────
        preflight = preflight_count_tokens(client, model, history, system_prompt)
        monthly_used_now = data["monthly"].get(this_month, {}).get("cost", 0.0)
        budget_left = MONTHLY_BUDGET - monthly_used_now
        print(f"  📡 Preflight → ~{preflight['input_tokens']:,} input tokens | "
              f"est. input cost ${preflight['predicted_cost']:.5f} | "
              f"budget left ${budget_left:.4f}")

        # Compress history if token count (from API) exceeds threshold
        if preflight["input_tokens"] > SUMMARY_THRESHOLD:
            history.pop()   # remove user msg before compressing
            history = summarise_history(history, client)
            history.append({"role": "user", "content": user_input})
            # Recount after compression
            preflight = preflight_count_tokens(client, model, history, system_prompt)
            print(f"  📡 After compression → ~{preflight['input_tokens']:,} tokens")

        try:
            response = client.messages.create(
                model=model,
                max_tokens=MAX_OUTPUT_TOKENS,
                system=system_prompt,
                messages=history
            )
        except Exception as e:
            print(f"  ❌ API error: {e}")
            history.pop()
            continue

        reply = response.content[0].text
        in_tok  = response.usage.input_tokens
        out_tok = response.usage.output_tokens

        cost = record_usage(data, model, in_tok, out_tok)
        session_cost  += cost
        session_in    += in_tok
        session_out   += out_tok
        session_calls += 1

        history.append({"role": "assistant", "content": reply})

        # Per-message stats
        model_short = model.split("-")[1]
        daily_used  = data["daily"].get(str(date.today()), {}).get("cost", 0.0)
        print(f"\n  Claude: {reply}")
        print(f"\n  ┌─ [{model_short}] in={in_tok} out={out_tok} "
              f"cost=${cost:.5f} | today=${daily_used:.4f} | "
              f"month=${data['monthly'].get(this_month,{}).get('cost',0):.4f} ─┐")

    # End of session report
    end_of_day_report(data, session_in, session_out, session_cost, session_calls)


if __name__ == "__main__":
    main()
