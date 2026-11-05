# Sales__SalesOrderHeaderSalesReason

**Type:** table | **Domain:** Sales | **Rows:** 27,647 | **SQL name:** `Sales__SalesOrderHeaderSalesReason`

Cross-reference mapping sales orders to the purchase reasons given (online orders).

**Primary key:** SalesOrderID, SalesReasonID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SalesOrderID | INTEGER | PK, FK -> Sales__SalesOrderHeader.SalesOrderID, NOT NULL |  | range 43697 .. 75123 |
| SalesReasonID | INTEGER | PK, FK -> Sales__SalesReason.SalesReasonID, NOT NULL |  | range 1 .. 10 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-05-30T00:00:00 .. 2025-06-29T00:00:00 |

## Relationships

- Sales__SalesOrderHeaderSalesReason.SalesReasonID = Sales__SalesReason.SalesReasonID  [declared]
- Sales__SalesOrderHeaderSalesReason.SalesOrderID = Sales__SalesOrderHeader.SalesOrderID  [declared]

## Example queries

**Purchase reasons given by customers**

```sql
SELECT sr.Name AS reason, sr.ReasonType, COUNT(*) AS orders
FROM Sales__SalesOrderHeaderSalesReason x
JOIN Sales__SalesReason sr ON sr.SalesReasonID = x.SalesReasonID
GROUP BY sr.Name, sr.ReasonType
ORDER BY orders DESC;
```

