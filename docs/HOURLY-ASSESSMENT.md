# Hourly assessment contract

`windows.json` version 7 adds an `hourly_assessment` descriptor to every
destination. Its `path` points to a lazy-loaded `hourly/<spot>.json` payload so
the initial mobile view does not download every chart series. The payload is
an engine-owned input for charts and tables. Frontends must not reimplement
`rules.yaml`.

## Safety boundary

An hourly record describes conditions at one destination during one hour, with
the conservative `transit` phase. It is never a navigation-window decision.
The explicit `is_window_decision: false` marker prevents a green hour from
being presented as a Family GO. Only records in `windows` validate a complete
outing with duration, departure, destination, return and daylight checks.

`condition_state` can be:

- `family`: within standard Family limits for that hour;
- `prudent`: outside standard limits but within the configured prudent tier;
- `watch`: a review-only uncertainty-band result, never a Family GO;
- `no_go`: outside all permitted hourly tiers or affected by a hard veto.

## Wind and gust provenance

`display_speed_kmh`, `display_gust_kmh`, direction and gust delta always come
from the same `display_source`. A frontend may therefore draw a wind-to-gust
ribbon without creating a physically false delta from two different models.
The full per-model series remain in the destination forecast JSON and are not
duplicated into `windows.json`.

The independent `max_speed_kmh` and `max_gust_kmh` remain available for audit
and threshold explanations; they must not be combined into a gust-delta ribbon.

## Reasons and waves

`reasons` contains every material outcome cause, not just the first blocker.
Each cause carries a stable code, French and English text, severity, and the
blocking wave source/pair when applicable. This allows a NO-GO explanation to
show both a gust veto and a short-period sea when both are present.

The display Hs/Tp pair comes from the blocking wave source when one exists,
otherwise from the conservative representative source selected by the engine.
All original Hs/Tp model pairs remain available in the destination forecast
JSON.

## Confidence

`confidence` is model agreement/forecast quality (`High`, `Medium`, or `Low`).
It is independent from `condition_state`: an unfavorable forecast may still
have high confidence.
