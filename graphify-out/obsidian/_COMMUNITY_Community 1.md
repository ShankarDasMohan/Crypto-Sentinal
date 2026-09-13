---
type: community
cohesion: 0.40
members: 5
---

# Community 1

**Cohesion:** 0.40 - moderately connected
**Members:** 5 nodes

## Members
- [[Feature 1 rate of change of price over a window. prices ordered list of…]] - rationale - spark/features.py
- [[Feature 2 z-score of current volume vs a rolling historical window (e.g. 1hr…]] - rationale - spark/features.py
- [[features.py]] - code - spark/features.py
- [[price_velocity()]] - code - spark/features.py
- [[volume_surge_zscore()]] - code - spark/features.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_1
SORT file.name ASC
```
