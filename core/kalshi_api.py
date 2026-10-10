"""Kalshi market data in pmapi's shape (read-only). Stdlib only.

PROTECTED CORE — the trading agent must not edit files under core/.

Draft adapter (kalshi branch, operator 2026-10-10). Not wired in yet:
nothing imports this module. It exposes the same functions as pmapi.py
(gamma_markets, gamma_market, clob_book, best_prices, market_tokens) and
reshapes Kalshi's public trade API into the gamma/CLOB records the rest of
core/ already reads, so scan, ledger, forecast and resolve could run on it
unchanged:
  market id      = Kalshi ticker
  outcomes       = ["Yes", "No"], token ids "<ticker>:yes" / "<ticker>:no"
  outcomePrices  = settled result (1/0) or the yes mid (last price if no book)
  endDate        = expected_expiration_time when Kalshi gives one (sports
                   markets close days after the game), else close_time
  volume24hr / volumeNum = contracts traded ($1 notional each, not USD)
  liquidityNum   = open interest in contracts (Kalshi has no liquidity field)
  book           = Kalshi lists bids only; a Yes ask is 1 - best No bid
Gamma query params are emulated: closed, end_date_min/max, order, ascending,
volume_num_min, liquidity_num_min, limit, offset. tag_id / related_tags have
no Kalshi equivalent and return no markets. series_ticker (a Kalshi series,
or a comma-separated list or Python list of them) is passed through to
Kalshi; it is the way to reach a category, since the unfiltered universe is
over 40k open markets, about 70% sports, and is capped at MAX_UNIVERSE.
Multivariate combo markets are
excluded. Numeric (Polymarket) market ids raise at once, so resolve.py would
leave the archived Polymarket rows alone instead of querying Kalshi for them.
"""
import datetime as dt
import json

from pmapi import get_json

VENUE = "kalshi"  # strategy/discovery.py reads this off the pmapi module
KALSHI = "https://api.elections.kalshi.com/trade-api/v2"
MAX_UNIVERSE = 3000  # markets paged per distinct query window
CLOSE_SLACK = dt.timedelta(days=14)  # close_time may trail the event
CLOSED = {"closed", "determined", "settled", "finalized"}
_universe_cache = {}


def _ts(value):
    """ISO-8601 string -> aware datetime, None when missing or unparseable."""
    if not value:
        return None
    try:
        return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _iso(t):
    return t.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def to_gamma(k):
    """Reshape one Kalshi market into the gamma fields core/ reads."""
    ticker = k["ticker"]
    status = k.get("status", "")
    result = (k.get("result") or "").lower()
    bid, ask = _num(k.get("yes_bid_dollars")), _num(k.get("yes_ask_dollars"))
    if result in ("yes", "no"):
        yes = 1.0 if result == "yes" else 0.0
    elif bid and ask and ask > 0:
        yes = (bid + ask) / 2
    else:
        yes = _num(k.get("last_price_dollars")) or 0.0
    close, expected = _ts(k.get("close_time")), _ts(k.get("expected_expiration_time"))
    end = expected if expected and (not close or expected < close) else close
    question = k.get("title") or ticker
    sub = k.get("yes_sub_title") or ""
    if sub and sub.lower() not in question.lower():
        question = f"{question} [{sub}]"
    settled = _ts(k.get("settlement_ts"))
    closed_at = settled or (close if status in CLOSED else None)
    return {
        "id": ticker,
        "question": question,
        "slug": ticker,
        "description": k.get("rules_primary") or "",
        "endDate": _iso(end) if end else None,
        "closed": status in CLOSED,
        "closedTime": _iso(closed_at) if closed_at else None,
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps([f"{yes:.4f}", f"{1 - yes:.4f}"]),
        "clobTokenIds": json.dumps([f"{ticker}:yes", f"{ticker}:no"]),
        "volume24hr": _num(k.get("volume_24h_fp")) or 0.0,
        "volumeNum": _num(k.get("volume_fp")) or 0.0,
        "liquidityNum": _num(k.get("open_interest_fp")) or 0.0,
        "events": [{"id": k.get("event_ticker"), "slug": k.get("event_ticker")}],
        "venue": "kalshi",
    }


def _universe(status, min_end, max_end, series=None):
    """Every market in a close-time window (optionally one series), paged by
    cursor and cached."""
    key = (status, min_end, max_end, series)
    if key in _universe_cache:
        return _universe_cache[key]
    params = {"status": status, "limit": 1000, "mve_filter": "exclude"}
    if series:
        params["series_ticker"] = series
    if min_end:
        params["min_close_ts"] = int(min_end.timestamp())
    if max_end:
        params["max_close_ts"] = int((max_end + CLOSE_SLACK).timestamp())
    out, cursor = [], None
    while len(out) < MAX_UNIVERSE:
        page = get_json(f"{KALSHI}/markets", dict(params, cursor=cursor) if cursor else params)
        out.extend(to_gamma(k) for k in page.get("markets", []))
        cursor = page.get("cursor")
        if not cursor or not page.get("markets"):
            break
    _universe_cache[key] = out
    return out


def gamma_markets(**params):
    if params.get("tag_id") or params.get("related_tags"):
        return []
    closed = str(params.get("closed", "false")).lower() == "true"
    min_end, max_end = _ts(params.get("end_date_min")), _ts(params.get("end_date_max"))
    status = "settled" if closed else "open"
    series = params.get("series_ticker")
    if series:
        if isinstance(series, str):
            series = series.split(",")
        rows = [m for s in series if s.strip()
                for m in _universe(status, min_end, max_end, s.strip())]
    else:
        rows = _universe(status, min_end, max_end)
    vol_min = _num(params.get("volume_num_min")) or 0
    liq_min = _num(params.get("liquidity_num_min")) or 0
    picked = []
    for m in rows:
        end = _ts(m["endDate"])
        if min_end and (not end or end < min_end):
            continue
        if max_end and (not end or end > max_end):
            continue
        if m["volumeNum"] < vol_min or m["liquidityNum"] < liq_min:
            continue
        picked.append(m)
    order = params.get("order")
    if order in ("endDate", "volume24hr", "liquidity", "volume"):
        field = {"liquidity": "liquidityNum", "volume": "volumeNum"}.get(order, order)
        desc = str(params.get("ascending", "true")).lower() == "false"
        blank = "" if field == "endDate" else 0.0
        picked.sort(key=lambda m: m[field] or blank, reverse=desc)
    offset = int(params.get("offset") or 0)
    limit = int(params.get("limit") or 100)
    return picked[offset:offset + limit]


def gamma_market(market_id):
    if str(market_id).isdigit():
        raise RuntimeError(f"{market_id} is a Polymarket id, not a Kalshi ticker")
    return to_gamma(get_json(f"{KALSHI}/markets/{market_id}")["market"])


def clob_book(token_id):
    ticker, _, side = str(token_id).rpartition(":")
    if side not in ("yes", "no") or not ticker:
        raise RuntimeError(f"{token_id} is not a Kalshi token id")
    book = get_json(f"{KALSHI}/markets/{ticker}/orderbook").get("orderbook_fp") or {}
    own = book.get(f"{side}_dollars") or []
    other = book.get(f"{'no' if side == 'yes' else 'yes'}_dollars") or []
    return {
        "bids": [{"price": p, "size": s} for p, s in own],
        "asks": [{"price": f"{1 - float(p):.4f}", "size": s} for p, s in other],
    }


def best_prices(token_id):
    """Return (best_bid, best_ask) for a Kalshi token, None if side empty."""
    book = clob_book(token_id)
    bids = [float(b["price"]) for b in book.get("bids", [])]
    asks = [float(a["price"]) for a in book.get("asks", [])]
    return (max(bids) if bids else None, min(asks) if asks else None)


def market_tokens(market):
    """Map outcome name -> token id for a reshaped market record."""
    outcomes = json.loads(market.get("outcomes", "[]"))
    token_ids = json.loads(market.get("clobTokenIds", "[]"))
    return dict(zip(outcomes, token_ids))
