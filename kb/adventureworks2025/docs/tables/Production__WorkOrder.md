# Production__WorkOrder

**Type:** table | **Domain:** Production | **Rows:** 72,591 | **SQL name:** `Production__WorkOrder`

Manufacturing work orders: product, quantity to build, scrapped quantity and dates.

**Synonyms:** work orders, production orders, manufacturing orders, jobs

**Primary key:** WorkOrderID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| WorkOrderID | INTEGER | PK, NOT NULL |  | range 1 .. 72591 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 3 .. 999 |
| OrderQty | INTEGER | NOT NULL | Product quantity to build. | range 1 .. 39570, avg 62.0975 |
| StockedQty | INTEGER | NOT NULL | Quantity built and put in inventory (= OrderQty - ScrappedQty). | range 1 .. 39570, avg 61.9508 |
| ScrappedQty | INTEGER | NOT NULL | Quantity that failed inspection. | range 0 .. 673, avg 0.146726 |
| StartDate | TEXT | NOT NULL | Work order start date. | range 2022-06-02T00:00:00 .. 2025-06-01T00:00:00 |
| EndDate | TEXT |  | Work order end date. | range 2022-06-12T00:00:00 .. 2025-06-16T00:00:00 |
| DueDate | TEXT | NOT NULL | Work order due date. | range 2022-06-13T00:00:00 .. 2025-06-12T00:00:00 |
| ScrapReasonID | INTEGER | FK -> Production__ScrapReason.ScrapReasonID | Reason for scrapping (NULL when nothing was scrapped). Join Production__ScrapReason. | range 1 .. 16; 99.0% null |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-06-12T00:00:00 .. 2025-06-16T00:00:00 |

## Relationships

- Production__WorkOrder.ProductID = Production__Product.ProductID  [declared]
- Production__WorkOrder.ScrapReasonID = Production__ScrapReason.ScrapReasonID  [declared]
- Production__WorkOrderRouting.WorkOrderID = Production__WorkOrder.WorkOrderID  [declared]
- Production__TransactionHistory.ReferenceOrderID = Production__WorkOrder.WorkOrderID AND (Production__TransactionHistory.TransactionType = 'W')  [curated; Work order behind a manufacturing transaction.]
- Production__TransactionHistoryArchive.ReferenceOrderID = Production__WorkOrder.WorkOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'W')  [kg; Archived Inventory Transaction for work order Work Order]

## Business definitions

- **Scrap rate**: Share of work-order quantity that failed inspection.

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

