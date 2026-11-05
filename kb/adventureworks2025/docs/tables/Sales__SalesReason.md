# Sales__SalesReason

**Type:** table | **Domain:** Sales | **Rows:** 10 | **SQL name:** `Sales__SalesReason`

Lookup of reasons customers give for a purchase (price, promotion, advertising, quality, ...).

**Primary key:** SalesReasonID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SalesReasonID | INTEGER | PK, NOT NULL |  | range 1 .. 10 |
| Name | TEXT | NOT NULL |  | values: 'Television  Advertisement', 'Sponsorship', 'Review', 'Quality', 'Price', 'Other', 'On Promotion', 'Manufacturer', 'Magazine Advertisement', 'Demo Event' |
| ReasonType | TEXT | NOT NULL | Category of the reason: Marketing, Promotion or Other. | values: 'Other' (5), 'Marketing' (4), 'Promotion' (1) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Sales__SalesOrderHeaderSalesReason.SalesReasonID = Sales__SalesReason.SalesReasonID  [declared]

## Example queries

**Purchase reasons given by customers**

```sql
SELECT sr.Name AS reason, sr.ReasonType, COUNT(*) AS orders
FROM Sales__SalesOrderHeaderSalesReason x
JOIN Sales__SalesReason sr ON sr.SalesReasonID = x.SalesReasonID
GROUP BY sr.Name, sr.ReasonType
ORDER BY orders DESC;
```

