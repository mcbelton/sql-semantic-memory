# Production__ScrapReason

**Type:** table | **Domain:** Production | **Rows:** 16 | **SQL name:** `Production__ScrapReason`

Manufacturing failure (scrap) reasons.

**Primary key:** ScrapReasonID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ScrapReasonID | INTEGER | PK, NOT NULL |  | range 1 .. 16 |
| Name | TEXT | NOT NULL |  | values: 'Brake assembly not as ordered', 'Color incorrect', 'Drill pattern incorrect', 'Drill size too large', 'Drill size too small', 'Gouge in metal', 'Handling damage', 'Paint process failed', 'Primer process failed', 'Seat assembly not as ordered', 'Stress test failed', 'Thermoform temperature too high', 'Thermoform temperature too low', 'Trim length too long', 'Trim length too short', 'Wheel misaligned' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__WorkOrder.ScrapReasonID = Production__ScrapReason.ScrapReasonID  [declared]

**Unique indexes:** Production__ScrapReason__AK_ScrapReason_Name (Name)

## Example queries

**Scrap quantity and scrap rate by scrap reason**

```sql
SELECT sr.Name AS scrap_reason, SUM(w.ScrappedQty) AS scrapped_units,
       ROUND(100.0 * SUM(w.ScrappedQty) / SUM(w.OrderQty), 2) AS scrap_pct_of_ordered
FROM Production__WorkOrder w
JOIN Production__ScrapReason sr ON sr.ScrapReasonID = w.ScrapReasonID
GROUP BY sr.Name
ORDER BY scrapped_units DESC;
```

