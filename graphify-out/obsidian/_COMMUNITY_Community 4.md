---
type: community
cohesion: 1.00
members: 2
---

# Community 4

**Cohesion:** 1.00 - tightly connected
**Members:** 2 nodes

## Members
- [[001_create_tables.sql]] - code - dbt/001_create_tables.sql
- [[raw_trades]] - code - dbt/001_create_tables.sql

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_4
SORT file.name ASC
```
