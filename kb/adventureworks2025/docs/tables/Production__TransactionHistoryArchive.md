# Production__TransactionHistoryArchive

**Type:** table | **Domain:** Production | **Rows:** 89,253 | **SQL name:** `Production__TransactionHistoryArchive`

Inventory transactions before 2024-07-30 (archive of Production__TransactionHistory, same columns).

**Primary key:** TransactionID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| TransactionID | INTEGER | PK, NOT NULL |  | range 1 .. 89253 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 999 |
| ReferenceOrderID | INTEGER | NOT NULL |  | range 1 .. 53449, avg 35121.2 |
| ReferenceOrderLineID | INTEGER | NOT NULL |  | range 0 .. 72, avg 6.77298 |
| TransactionDate | TEXT | NOT NULL |  | range 2022-04-15T00:00:00 .. 2024-07-29T00:00:00 |
| TransactionType | TEXT | NOT NULL | Type of transaction. | codes: W=Work order, S=Sales order, P=Purchase order; values: 'S' (46,742), 'W' (41,589), 'P' (922) |
| Quantity | INTEGER | NOT NULL |  | range 1 .. 39570, avg 34.26 |
| ActualCost | NUMERIC | NOT NULL |  | range 0 .. 3578.27, avg 396.624 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-15T00:00:00 .. 2024-07-29T00:00:00 |

## Relationships

- Production__TransactionHistoryArchive.ProductID = Production__Product.ProductID  [inferred]
- Production__TransactionHistoryArchive.ReferenceOrderID = Sales__SalesOrderHeader.SalesOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'S')  [kg; Archived Inventory Transaction for sales order Sales Order]
- Production__TransactionHistoryArchive.ReferenceOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'P')  [kg; Archived Inventory Transaction for purchase order Purchase Order]
- Production__TransactionHistoryArchive.ReferenceOrderID = Production__WorkOrder.WorkOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'W')  [kg; Archived Inventory Transaction for work order Work Order]

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

