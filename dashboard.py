import anthropic
import requests
import feedparser
import yfinance as yf
from datetime import datetime
import os

# ── CONFIG ───────────────────────────────────────────────────────────────────
FRED_API_KEY      = "e0c08ff800fe20fe7ee89c3e5f101a37"
ANTHROPIC_API_KEY = "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" 
OUTPUT_FILE       = os.path.join(os.path.expanduser("~"), "Desktop", "dashboard.html")

# ── STEP 1: FETCH MACRO DATA FROM FRED ───────────────────────────────────────
def get_fred(series_id, label):
    url = (f"https://api.stlouisfed.org/fred/series/observations"
           f"?series_id={series_id}&api_key={FRED_API_KEY}"
           f"&sort_order=desc&limit=1&file_type=json")
    try:
        r = requests.get(url, timeout=10).json()
        val = r["observations"][0]["value"]
        return f"{label}: {val}"
    except:
        return f"{label}: unavailable"

def fetch_macro():
    return [
        get_fred("FEDFUNDS",  "Fed Funds Rate (%)"),
        get_fred("CPIAUCSL",  "CPI Index"),
        get_fred("UNRATE",    "Unemployment Rate (%)"),
        get_fred("DCOILWTICO","WTI Crude Oil Price ($/barrel)"),
        get_fred("T10Y2Y",    "10Y-2Y Treasury Spread"),
    ]

# ── STEP 2: FETCH NEWS HEADLINES ─────────────────────────────────────────────
def fetch_news():
    feeds = [
        "https://feeds.reuters.com/reuters/businessNews",
        "https://feeds.content.dowjones.io/public/rss/mw_realtimeheadlines",
        "https://rss.nytimes.com/services/xml/rss/nyt/Economy.xml",
    ]
    headlines = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:4]:
                headlines.append(entry.title)
        except:
            pass
    return headlines[:12]

# ── STEP 3: FETCH MARKET PRICES ──────────────────────────────────────────────
def fetch_markets():
    tickers = {
        "S&P 500":       "^GSPC",
        "Nasdaq":        "^IXIC",
        "Dow Jones":     "^DJI",
        "10Y Treasury":  "^TNX",
        "Gold":          "GC=F",
        "Crude Oil":     "CL=F",
        "USD Index":     "DX-Y.NYB",
        "VIX":           "^VIX",
    }
    results = []
    for name, ticker in tickers.items():
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="2d")
            if len(hist) >= 2:
                prev  = hist["Close"].iloc[-2]
                curr  = hist["Close"].iloc[-1]
                chg   = ((curr - prev) / prev) * 100
                arrow = "▲" if chg >= 0 else "▼"
                results.append({
                    "name":  name,
                    "price": f"{curr:.2f}",
                    "change": f"{arrow} {abs(chg):.2f}%",
                    "up":    chg >= 0
                })
        except:
            results.append({"name": name, "price": "N/A", "change": "—", "up": True})
    return results

# ── STEP 4: SEND EVERYTHING TO CLAUDE FOR ANALYSIS ───────────────────────────
def analyze_with_claude(macro, headlines, markets):
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    market_summary = "\n".join([f"{m['name']}: {m['price']} ({m['change']})" for m in markets])
    macro_summary  = "\n".join(macro)
    news_summary   = "\n".join([f"- {h}" for h in headlines])

    prompt = f"""You are a senior macro analyst at a top investment bank writing a daily morning situation deck.

MACRO DATA:
{macro_summary}

MARKET PRICES:
{market_summary}

NEWS HEADLINES:
{news_summary}

Write a concise morning briefing with these exact sections:

SITUATION OVERVIEW
2-3 sentences on the single most important macro story right now and what it means for markets.

TOP 3 THEMES
For each: theme name, one sentence explanation, and which assets are most affected.

MARKET IMPLICATIONS
What should an analyst watch today? Any notable divergences or risks?

FED WATCH
Based on the macro data and news, characterize current Fed policy stance in 1-2 sentences.

ANALYST TONE
Overall market sentiment today: Risk-On / Risk-Off / Mixed — and why in one sentence.

Keep it sharp, technical, and direct. No fluff."""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    return message.content[0].text

# ── STEP 5: BUILD THE HTML DASHBOARD ─────────────────────────────────────────
def build_html(macro, headlines, markets, analysis):
    now = datetime.now().strftime("%A, %B %d, %Y — %I:%M %p")

    market_cards = ""
    for m in markets:
        color = "#16a34a" if m["up"] else "#dc2626"
        bg    = "#f0fdf4" if m["up"] else "#fef2f2"
        market_cards += f"""
        <div style="background:{bg};border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;min-width:130px;">
          <div style="font-size:11px;color:#6b7280;font-weight:500;margin-bottom:4px;">{m['name']}</div>
          <div style="font-size:18px;font-weight:700;color:#111827;">{m['price']}</div>
          <div style="font-size:12px;font-weight:600;color:{color};">{m['change']}</div>
        </div>"""

    macro_rows = "".join([f"<li style='padding:4px 0;border-bottom:1px solid #f3f4f6;font-size:13px;'>{m}</li>" for m in macro])
    news_rows  = "".join([f"<li style='padding:5px 0;border-bottom:1px solid #f3f4f6;font-size:13px;'>• {h}</li>" for h in headlines])

    analysis_html = ""
    for line in analysis.split("\n"):
        line = line.strip()
        if not line:
            analysis_html += "<br>"
        elif line.isupper() or (len(line) < 40 and line.endswith(("OVERVIEW","THEMES","IMPLICATIONS","WATCH","TONE"))):
            analysis_html += f"<h3 style='color:#1e3a5f;font-size:13px;font-weight:700;margin:16px 0 4px;text-transform:uppercase;letter-spacing:0.05em;'>{line}</h3>"
        else:
            analysis_html += f"<p style='margin:4px 0;font-size:13px;line-height:1.6;color:#374151;'>{line}</p>"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Macro Situation Deck</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f8fafc; color: #111827; }}
  .header {{ background: #1e3a5f; color: white; padding: 20px 32px; display: flex; justify-content: space-between; align-items: center; }}
  .header h1 {{ font-size: 20px; font-weight: 700; letter-spacing: 0.05em; }}
  .header .date {{ font-size: 12px; opacity: 0.7; }}
  .container {{ max-width: 1200px; margin: 0 auto; padding: 24px 32px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 20px; }}
  .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 10px; padding: 20px; }}
  .card h2 {{ font-size: 11px; font-weight: 700; color: #6b7280; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }}
  .markets {{ display: flex; flex-wrap: wrap; gap: 10px; margin-top: 20px; }}
  .analysis-card {{ background: white; border: 2px solid #1e3a5f; border-radius: 10px; padding: 20px; margin-top: 20px; }}
  .analysis-card h2 {{ font-size: 11px; font-weight: 700; color: #1e3a5f; text-transform: uppercase; letter-spacing: 0.08em; margin-bottom: 12px; }}
  ul {{ list-style: none; padding: 0; }}
  .badge {{ display: inline-block; background: #1e3a5f; color: white; font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; margin-bottom: 12px; }}
</style>
</head>
<body>
<div class="header">
  <h1>MACRO SITUATION DECK</h1>
  <div class="date">Generated: {now}</div>
</div>
<div class="container">
  <span class="badge">LIVE DATA</span>
  <div class="markets">{market_cards}</div>
  <div class="grid">
    <div class="card">
      <h2>Macro Indicators (FRED)</h2>
      <ul>{macro_rows}</ul>
    </div>
    <div class="card">
      <h2>Top Headlines</h2>
      <ul>{news_rows}</ul>
    </div>
  </div>
  <div class="analysis-card">
    <h2>AI Analysis — Claude Opus</h2>
    {analysis_html}
  </div>
</div>
</body>
</html>"""
    return html

# ── MAIN ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("Fetching macro data...")
    macro = fetch_macro()

    print("Fetching news headlines...")
    headlines = fetch_news()

    print("Fetching market prices...")
    markets = fetch_markets()

    print("Sending to Claude for analysis...")
    analysis = analyze_with_claude(macro, headlines, markets)

    print("Building dashboard...")
    html = build_html(macro, headlines, markets, analysis)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDone! Dashboard saved to: {OUTPUT_FILE}")
    print("Open that file in your browser to view it.")