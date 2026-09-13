---
type: community
cohesion: 0.70
members: 5
---

# Community 0

**Cohesion:** 0.70 - tightly connected
**Members:** 5 nodes

## Members
- [[binance_producer.py]] - code - ingestion/binance_producer.py
- [[on_close()]] - code - ingestion/binance_producer.py
- [[on_error()]] - code - ingestion/binance_producer.py
- [[on_message()]] - code - ingestion/binance_producer.py
- [[run()]] - code - ingestion/binance_producer.py

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_0
SORT file.name ASC
```
