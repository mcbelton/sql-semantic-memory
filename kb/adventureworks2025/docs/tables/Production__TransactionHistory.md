# Production__TransactionHistory

**Type:** table | **Domain:** Production | **Rows:** 113,443 | **SQL name:** `Production__TransactionHistory`

Inventory transactions (sales, purchases, work orders) from 2024-07-30 onward. Older transactions are in Production__TransactionHistoryArchive; UNION ALL both for full history.

**Synonyms:** inventory transactions, stock movements

**Primary key:** TransactionID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| TransactionID | INTEGER | PK, NOT NULL |  | range 100000 .. 213442 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 999 |
| ReferenceOrderID | INTEGER | NOT NULL | Id of the originating order: SalesOrderID, PurchaseOrderID or WorkOrderID depending on TransactionType. | range 417 .. 75123, avg 57587.8 |
| ReferenceOrderLineID | INTEGER | NOT NULL | Line number of the originating order. | range 0 .. 71, avg 4.67129 |
| TransactionDate | TEXT | NOT NULL | Date of the transaction. | range 2024-07-30T00:00:00 .. 2025-08-02T00:00:00 |
| TransactionType | TEXT | NOT NULL | Type of transaction. | codes: W=Work order, S=Sales order, P=Purchase order; values: 'S' (74,575), 'W' (31,002), 'P' (7,866) |
| Quantity | INTEGER | NOT NULL | Product quantity. | range 1 .. 39270, avg 35.0591 |
| ActualCost | NUMERIC | NOT NULL | Product cost. | range 0 .. 2443.35, avg 240.714 |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-07-30T00:00:00 .. 2025-08-02T00:00:00 |

## Relationships

- Production__TransactionHistory.ProductID = Production__Product.ProductID  [declared]
- Production__TransactionHistory.ReferenceOrderID = Sales__SalesOrderHeader.SalesOrderID AND (Production__TransactionHistory.TransactionType = 'S')  [curated; Sales order behind a sales transaction.]
- Production__TransactionHistory.ReferenceOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID AND (Production__TransactionHistory.TransactionType = 'P')  [curated; Purchase order behind a purchase transaction.]
- Production__TransactionHistory.ReferenceOrderID = Production__WorkOrder.WorkOrderID AND (Production__TransactionHistory.TransactionType = 'W')  [curated; Work order behind a manufacturing transaction.]

## Business definitions

- **Full inventory transaction history**: Production__TransactionHistory holds transactions from 2024-07-30; Production__TransactionHistoryArchive holds earlier ones. UNION ALL both tables for complete history.

## Example queries

**Full inventory transaction history of one product (current + archive)**

```sql
SELECT t.TransactionDate, t.TransactionType, t.Quantity, t.ActualCost, t.ReferenceOrderID
FROM (
  SELECT ProductID, TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID
  FROM Production__TransactionHistory
  UNION ALL
  SELECT ProductID, TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID
  FROM Production__TransactionHistoryArchive
) t
JOIN Production__Product p ON p.ProductID = t.ProductID
WHERE p.ProductNumber = 'BK-M68B-42'
ORDER BY t.TransactionDate;
```

