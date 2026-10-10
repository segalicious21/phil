"""Polymarket API helpers (read-only). Stdlib only.

PROTECTED CORE — the trading agent must not edit files under core/.

Venue switch (kalshi branch, operator 2026-10-10): Polymarket answers HTTP
451 in this operator's region, so the default venue here is Kalshi and the
market-data functions delegate to core/kalshi_api.py, which returns the same
gamma/CLOB shapes. PHIL_VENUE=polymarket restores the original calls.
"""
import json
import os
import time
import urllib.parse
import urllib.request

GAMMA = "https://gamma-api.polymarket.com"
CLOB = "https://clob.polymarket.com"
UA = {"User-Agent": "pearl-explorations-paper-trader/0.1"}


def get_json(url, params=None, retries=3):
    if params:
        url = url + "?" + urllib.parse.urlencode(params)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except Exception as e:  # noqa: BLE001 — retry then surface
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"GET {url} failed after {retries} tries: {last_err}")


def gamma_markets(**params):
    return get_json(f"{GAMMA}/markets", params)


def gamma_market(market_id):
    return get_json(f"{GAMMA}/markets/{market_id}")


def clob_book(token_id):
    return get_json(f"{CLOB}/book", {"token_id": token_id})


def best_prices(token_id):
    """Return (best_bid, best_ask) for a CLOB token, None if side empty."""
    book = clob_book(token_id)
    bids = [float(b["price"]) for b in book.get("bids", [])]
    asks = [float(a["price"]) for a in book.get("asks", [])]
    return (max(bids) if bids else None, min(asks) if asks else None)


def market_tokens(market):
    """Map outcome name -> clob token id for a gamma market record."""
    outcomes = json.loads(market.get("outcomes", "[]"))
    token_ids = json.loads(market.get("clobTokenIds", "[]"))
    return dict(zip(outcomes, token_ids))


VENUE = os.environ.get("PHIL_VENUE", "kalshi").lower()

if VENUE == "kalshi":
    # Imported last: kalshi_api takes get_json from this module. The wrappers
    # look kalshi_api up at call time, so either module may be imported first.
    import kalshi_api

    def gamma_markets(**params):  # noqa: F811 — venue override
        return kalshi_api.gamma_markets(**params)

    def gamma_market(market_id):  # noqa: F811
        return kalshi_api.gamma_market(market_id)

    def clob_book(token_id):  # noqa: F811
        return kalshi_api.clob_book(token_id)

    def best_prices(token_id):  # noqa: F811
        return kalshi_api.best_prices(token_id)
