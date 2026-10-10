"""Market discovery — AGENT-EDITABLE.

This is my sensing layer. `core/scan.py` calls `queries()` and then applies the
protected admissibility filters (banned classes, resolution floor, price
bounds) to whatever comes back. I decide WHAT TO LOOK FOR; core decides what is
allowed. A query I write cannot let a banned market through, so I can explore
freely.

Why this file exists (operator, 2026-08-03): for two days I produced zero bets
and correctly logged "no qualifying candidate" every cycle. The cause was not
the market — it was that scan paged in endDate order through a near-term
universe thousands of sub-daily markets deep and never escaped day 0. My
candidate pool was an artifact of a tool I could not edit and could not see
into. Now I can. Use it: if the pool looks structurally wrong, change the
queries and say so in the retro.

Contract: return a list of dicts of gamma `/markets` query params. Optional
`_label` names the query in scan's stderr. Anything raising here falls back to
core's default query (loudly), so a bug degrades sensing but never blinds me.
Gamma params that work: closed, order (endDate|volume24hr|liquidity),
ascending, end_date_min, end_date_max, volume_num_min, liquidity_num_min,
tag_id, related_tags.

Venue (kalshi branch, operator 2026-10-10): when core/kalshi_api.py stands in
for pmapi, scan's pmapi module carries VENUE = "kalshi" and kalshi_queries()
runs instead. Kalshi has no tags; a category is reached by naming its series
(series_ticker). Volume and liquidity floors there count contracts ($1
notional each) and open interest, not USD.
"""
import datetime
import sys

# Kalshi series that resolve on an official print, verified live 2026-10-10
# (each had open markets; KXPCE and KXPPI do not exist on Kalshi). This is
# the Kalshi counterpart of the Polymarket econ tag below: BLS CPI family,
# the Fed decision, payrolls, unemployment, GDP, core PCE, jobless claims.
KALSHI_ECON_SERIES = ["KXCPI", "KXCPIYOY", "KXCPICORE", "KXCPICOREYOY",
                      "KXFED", "KXFEDDECISION", "KXPAYROLLS", "KXU3", "KXGDP",
                      "KXPCECORE", "KXJOBLESSCLAIMS"]
# Exchange-settled price brackets (ICE / Pyth). Thin books: the spread cap in
# strategy/policy.py does the filtering, so no volume floor here either.
KALSHI_COMMODITY_SERIES = ["KXWTI", "KXWTIW", "KXBRENTW", "KXGOLDW"]


def venue():
    return getattr(sys.modules.get("pmapi"), "VENUE", "polymarket")


def kalshi_queries(now, min_end, horizon, iso, base):
    today_end = min(horizon, now.replace(microsecond=0) + datetime.timedelta(hours=36))
    return [
        # 1-3 mirror the Polymarket lanes on Kalshi's unfiltered universe,
        # which is mostly sports and capped by core/kalshi_api.MAX_UNIVERSE.
        {**base, "_label": "kalshi-liquid-multiday", "order": "endDate",
         "ascending": "true", "volume_num_min": 50000},
        {**base, "_label": "kalshi-by-open-interest", "order": "liquidity",
         "ascending": "false", "liquidity_num_min": 20000},
        {"closed": "false", "_label": "kalshi-active-today", "order": "volume24hr",
         "ascending": "false", "end_date_min": iso(min_end),
         "end_date_max": iso(today_end)},
        # 4-5 reach categories by series, without a volume floor, for the same
        # reason as the Polymarket econ tag: mechanically resolving beats deep.
        {**base, "_label": "kalshi-econ-series", "order": "volume24hr",
         "ascending": "false", "series_ticker": ",".join(KALSHI_ECON_SERIES)},
        {**base, "_label": "kalshi-commodity-series", "order": "volume24hr",
         "ascending": "false", "series_ticker": ",".join(KALSHI_COMMODITY_SERIES)},
    ]


def queries(now, min_end, horizon, args, protected):
    iso = lambda t: t.strftime("%Y-%m-%dT%H:%M:%SZ")  # noqa: E731
    base = {"closed": "false", "end_date_min": iso(min_end),
            "end_date_max": iso(horizon)}
    if venue() == "kalshi":
        return kalshi_queries(now, min_end, horizon, iso, base)

    return [
        # 1. Well-covered events out to the horizon. The lifetime-volume floor
        #    is what lets pagination escape today; do NOT add a 24h-volume
        #    floor here — an event five days out legitimately has little volume
        #    today, which re-creates the blindness this file was made to fix.
        {**base, "_label": "liquid-multiday", "order": "endDate",
         "ascending": "true", "volume_num_min": 50000},

        # 2. Deep books regardless of date order — surfaces the biggest events
        #    in the window (ATP/WTA main draws, major-league fixtures) even if
        #    thousands of small markets resolve sooner.
        {**base, "_label": "by-liquidity", "order": "liquidity",
         "ascending": "false", "liquidity_num_min": 20000},

        # 3. Today's active markets, kept from the old behaviour so nothing
        #    imminent is lost: heavy recent trading, near-term resolution.
        {"closed": "false", "_label": "active-today", "order": "volume24hr",
         "ascending": "false", "end_date_min": iso(min_end),
         "end_date_max": iso(min(horizon, now.replace(microsecond=0) +
                                 __import__("datetime").timedelta(hours=36)))},

        # 4. Category-targeted, asymmetric floor (operator-notes.md 2026-08-05:
        #    a $20k econ market with a free official benchmark is worth more
        #    research time than a $400k tennis match with no reachable status
        #    source — queries 1-3 are volume/liquidity-first and bury these).
        #    tag_id 100328 = Polymarket's "Economy" tag; verified live
        #    2026-08-05 it surfaces Fed-rate-decision markets ($300k-590k
        #    volume24hr, FOMC tag 100478 is a subset) and GDP brackets
        #    ($700-2800 volume24hr, would never clear query 1's 50k floor).
        #    These resolve off an official print/vote, not a narrative read —
        #    the fact-finality profile the settled evidence favors. No volume
        #    floor here on purpose; thin but mechanically-resolving is the
        #    point. (climate-weather tag 1474 checked same day: 0 live
        #    markets currently, so not included — revisit if that changes.)
        {**base, "_label": "econ-tag", "tag_id": 100328, "order": "volume24hr",
         "ascending": "false"},
    ]
