import requests
import json
import time

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

symbols = ["RELIANCE", "TATAMOTORS", "TCS", "INFY"]
session = requests.Session()
quotes = {}

for s in symbols:
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{s}.NS?interval=5m&range=1d"
    try:
        r = session.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            d = r.json()
            meta = d["chart"]["result"][0]["meta"]
            quotes[s] = {
                "symbol": s,
                "price": meta.get("regularMarketPrice"),
                "high": meta.get("regularMarketDayHigh"),
                "low": meta.get("regularMarketDayLow"),
                "volume": meta.get("regularMarketVolume"),
                "timestamp": meta.get("regularMarketTime"),
            }
            print(f"Fetched {s}: {quotes[s]['price']}")
        else:
            print(f"Status {r.status_code} for {s}")
    except Exception as e:
        print(f"Error {s}: {e}")
    time.sleep(0.5)

print("\nFinal Quotes:")
print(json.dumps(quotes, indent=2))
