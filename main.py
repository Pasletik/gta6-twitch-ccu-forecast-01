"""gta6-twitch-ccu-forecast-01 entry in Python 3.13 (standard library only).

Forecasts the Grand Theft Auto VI Twitch category's concurrent viewers for
hours 2..24 of its release day (UTC), as five quantiles an hour, from the
case's hour-1 print plus the 38-42 past big launches in `comparables`.

Method (fitted and validated on the four practice cases only; nothing is
hardcoded to any launch, and the final case is computed the same way from
whatever case file it is given):

  For each comparable launch, take its release-day hourly curve and form the
  log-ratios d_h = ln(viewers at hour h) - ln(viewers at hour 1), h = 2..24.
  The day's shape is remarkably stable across launches once two things are
  matched: the launch's scale (its hour-1 print) and its pre-release hype
  (the last pre-release hour's viewers, relative to hour 1). So each
  comparable is weighted by a Gaussian kernel on both:

      w = exp(-((ln p1_comp - ln p1) / 1.25)^2)
        * exp(-((pre_comp - pre_target) / 0.20)^2)

  where pre = ln(last pre-release hour's viewers) - ln(hour-1 viewers).
  The pre-release factor is skipped when either side has no pre-release
  point. For each hour, the forecast is lognormal around the weighted mean
  of d_h with the weighted standard deviation shrunk by 0.70 (the raw
  cross-launch spread overstates the matched conditional spread):

      q_tau(h) = p1 * exp(mean_h + z_tau * 0.70 * sd_h)

  with z = (-1.645, -0.674, 0, 0.674, 1.645) at the levels
  (0.05, 0.25, 0.5, 0.75, 0.95), rounded to 2 decimals. If no comparable
  has a point for an hour, that hour falls back to the house baseline's
  persistence spread (0.15 * sqrt(h - 1) in log space).

Local practice result (scored with the pinball loss exactly as RULES.txt
defines it, against the SullyGnome hourly counts): mean loss 0.162 over
the four practice cases (p00 0.210, p01 0.147, p02 0.102, p03 0.188),
typical miss 27.0%, 90% coverage 0.88 -- against the house baseline's
0.387 loss / 82.7% miss / 0.78 coverage on the same cases.

How the grader runs it: `python3 -P -s /bot/main.py` (PYTHONHASHSEED=0)
in python:3.13-slim, standard library only: no network, no pip packages.
-P keeps this file's directory OFF sys.path, so a module shipped beside
main.py imports only after the sys.path line below.

What an entry must do:
  - read every <id>.in in the input directory (the grader runs one case at
    a time, with only that case's file there): JSON
    {"schema": "makefun/twitch-ccu-case/v1", "id", "game", "day_start",
    "checkpoint", "levels", "known", "forecast", "history",
    "history_hourly", "streams", "categories_hourly", "comparables",
    "notes"}, where `known` holds hour 1's print {hour: 1, from, until,
    viewers, channels, reads} and `forecast` lists the hours to forecast,
    2..24;
  - write <id>.out to the output directory: {"hours": [{"hour": 2, "q":
    [q05, q25, q50, q75, q95]}, ...]}, exactly 23 rows, hours 2..24 each
    once, no other key, each q five finite numbers above 0 and at most
    1e9 (viewers; fractions allowed), non-decreasing; at most 65,536
    bytes. Anything else is an invalid case, scored as if every quantile
    equalled hour 1's print, and an entry with an invalid case takes no
    prize.

Outside the grader's container, MAKEFUN_INPUT_DIR and MAKEFUN_OUTPUT_DIR
stand in for /input and /output:
    mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
"""

import json
import math
import os
import sys
from datetime import datetime
from pathlib import Path

# The grader's -P leaves /bot off sys.path: put it back first, so a module
# shipped beside this file imports.
sys.path.insert(0, str(Path(__file__).resolve().parent))

INPUT_DIR = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
OUTPUT_DIR = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))

# The quantile levels the contest scores, in the order each row lists them.
LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# The standard normal's quantile at each level.
Z = [-1.645, -0.674, 0.0, 0.674, 1.645]

# Kernel bandwidths (log units) for matching a comparable to the target:
# on the launch's scale (its hour-1 print) and on its pre-release hype.
BW_SCALE = 1.25
BW_PRE = 0.20
# The raw cross-launch spread overstates the matched conditional spread.
SD_SHRINK = 0.70
# The baseline's spread, used only when no comparable has a point for an hour.
BASELINE_SIGMA = 0.15


def parse_ts(text):
    """An ISO 8601 UTC timestamp to a datetime."""
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def round2(x):
    """x rounded to 2 decimals, half up, as JavaScript's Math.round(x * 100) / 100.

    A whole number comes back as an int, so json.dumps writes 1240 where
    JavaScript writes 1240 (not 1240.0).
    """
    scaled = x * 100
    whole = math.floor(scaled)
    if scaled - whole >= 0.5:
        whole += 1
    value = whole / 100
    return int(value) if value.is_integer() else value


def hour_offset(row_from, day_start):
    """Whole hours from day_start to a row's `from` timestamp (may be negative)."""
    return int((parse_ts(row_from) - day_start).total_seconds() // 3600)


def comparable_curves(case):
    """One entry per comparable with a usable hour-1 point.

    Each entry: {"s": ln(hour-1 viewers), "day": {offset: viewers} for the
    release day's hours 0..23, "pre": ln(last pre-release hour's viewers)
    - ln(hour-1 viewers), or None when it has no pre-release point}.
    """
    curves = []
    for comp in case.get("comparables") or []:
        day_start = parse_ts(comp["day_start"])
        day = {}
        pre_rows = []
        for row in comp.get("hourly") or []:
            viewers = row.get("viewers")
            if not viewers or viewers <= 0:
                continue
            off = hour_offset(row["from"], day_start)
            if 0 <= off < 24:
                day[off] = viewers
            elif off < 0:
                pre_rows.append((off, viewers))
        if 0 not in day:
            continue
        pre = None
        if pre_rows:
            # The latest pre-release point (largest offset below 0).
            pre_rows.sort()
            pre = math.log(pre_rows[-1][1]) - math.log(day[0])
        curves.append({"s": math.log(day[0]), "day": day, "pre": pre})
    return curves


def target_pre_ratio(case, p1):
    """ln(last pre-release hour's viewers) - ln(hour-1 viewers) for the target.

    From `history_hourly` (whole-hour means, present in practice and final
    cases alike). None when there is no pre-release point.
    """
    day_start = parse_ts(case["day_start"])
    last = None
    for row in case.get("history_hourly") or []:
        viewers = row.get("viewers")
        if not viewers or viewers <= 0:
            continue
        if parse_ts(row["from"]) < day_start:
            last = viewers
    if last is None:
        return None
    return math.log(last) - math.log(p1)


def fallback_quantiles(p1, h):
    """The house baseline's persistence forecast for one hour."""
    return [
        round2(p1 * math.exp(z * BASELINE_SIGMA * math.sqrt(h - 1)))
        for z in Z
    ]


def forecast_case(case, name):
    """The 23 forecast rows for one case."""
    first = next((k for k in case["known"] if k["hour"] == 1), None)
    if first is None:
        raise ValueError(f"{name} has no hour-1 print")
    p1 = max(1, first["viewers"])
    log_p1 = math.log(p1)
    curves = comparable_curves(case)
    pre_target = target_pre_ratio(case, p1)

    hours = []
    for row in case["forecast"]:
        h = row["hour"]
        pairs = []  # (log-ratio d_h, log-weight), sorted by d_h
        for cv in curves:
            day = cv["day"]
            if h - 1 not in day:
                continue
            d = math.log(day[h - 1]) - math.log(day[0])
            lw = -(((cv["s"] - log_p1) / BW_SCALE) ** 2)
            if pre_target is not None and cv["pre"] is not None:
                lw += -(((cv["pre"] - pre_target) / BW_PRE) ** 2)
            pairs.append((d, lw))
        if not pairs:
            hours.append({"hour": h, "q": fallback_quantiles(p1, h)})
            continue
        # Shift log-weights by their max before exponentiating, so a target
        # far outside every comparable's scale cannot underflow all weights
        # to zero (a crash here would invalidate the whole case).
        max_lw = max(lw for _, lw in pairs)
        pairs = [(d, math.exp(lw - max_lw)) for d, lw in pairs]
        pairs.sort()
        total_w = sum(w for _, w in pairs)
        if total_w <= 0:
            hours.append({"hour": h, "q": fallback_quantiles(p1, h)})
            continue
        mean = sum(d * w for d, w in pairs) / total_w
        var = sum(w * (d - mean) ** 2 for d, w in pairs) / total_w
        sd = math.sqrt(max(var, 0.0)) * SD_SHRINK
        # Insurance against a collapsed spread: if one comparable dominates
        # the kernel (an out-of-regime target), the weighted spread can
        # shrink to ~0 and the forecast would claim false certainty.
        sd = max(sd, 0.15)
        qs = []
        for z in Z:
            q = p1 * math.exp(mean + z * sd)
            q = min(max(q, 1.0), 1e9)
            qs.append(round2(q))
        for i in range(1, 5):
            qs[i] = max(qs[i], qs[i - 1])
        hours.append({"hour": h, "q": qs})
    return {"hours": hours}


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    # Every case file, in name order, so two runs write the same bytes.
    for path in sorted(INPUT_DIR.glob("*.in")):
        case = json.loads(path.read_text(encoding="utf-8"))
        forecast = forecast_case(case, path.name)
        (OUTPUT_DIR / f"{path.stem}.out").write_text(
            json.dumps(forecast, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    main()
