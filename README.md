# GTA VI Twitch CCU forecast — make.fun gta6-twitch-ccu-forecast-01

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Pasletik/gta6-twitch-ccu-forecast-01/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/Pasletik/gta6-twitch-ccu-forecast-01/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

My referral: [fdvwjd8e](https://make.fun/r/fdvwjd8e)

A program that forecasts how many people watch Grand Theft Auto VI live on
Twitch in each hour of its release day (2026-11-19 UTC), as five quantiles
an hour, from the first hour's viewer count. It runs offline, standard
library only, no network, no model calls.

## Method

For each of the 38–42 past big launches in the case's `comparables`, take
its release-day hourly curve and form the log-ratios to its own hour-1
print, `d_h = ln(viewers_h) - ln(viewers_1)`. The day's shape is stable
across launches once two things are matched: the launch's scale (its
hour-1 print) and its pre-release hype (the last pre-release hour's
viewers, relative to hour 1). Each comparable is weighted by a Gaussian
kernel on both (bandwidths 1.25 and 0.20 in log units). For each hour, the
forecast is lognormal around the weighted mean of `d_h`, with the weighted
standard deviation shrunk by 0.70. An hour with no comparable point falls
back to the house baseline's persistence spread.

## Local practice result

Scored with the pinball loss exactly as the rules define it, against the
SullyGnome hourly counts for the four practice launches (Wolverine, Red
Dead Redemption 2, God of War Ragnarök, Spider-Man 2):

| entry | loss | typical miss | 90% coverage |
| --- | --- | --- | --- |
| this program | **0.162** | 27.0% | 0.88 |
| house baseline (starter) | 0.387 | 82.7% | 0.78 |

Per case: p00 0.210, p01 0.147, p02 0.102, p03 0.188.

## Run locally

```sh
mkdir -p out
MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Reads every `*.in` in the input directory and writes one `<id>.out` per
case. Two runs on the same case write byte-identical output.
