---
type: community
cohesion: 1.00
members: 2
---

# Community 5

**Cohesion:** 1.00 - tightly connected
**Members:** 2 nodes

## Members
- [[002_create_feature_store.sql]] - code - dbt/002_create_feature_store.sql
- [[feature_store]] - code - dbt/002_create_feature_store.sql

## Live Query (requires Dataview plugin)

```dataview
TABLE source_file, type FROM #community/Community_5
SORT file.name ASC
```
