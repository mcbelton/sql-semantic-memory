# Purchasing__PurchaseOrderDetail

**Type:** table | **Domain:** Purchasing | **Rows:** 8,845 | **SQL name:** `Purchasing__PurchaseOrderDetail`

Purchase order lines (products ordered from vendors).

**Synonyms:** purchase order lines, PO lines

**Primary key:** PurchaseOrderID, PurchaseOrderDetailID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| PurchaseOrderID | INTEGER | PK, FK -> Purchasing__PurchaseOrderHeader.PurchaseOrderID, NOT NULL |  | range 1 .. 4012 |
| PurchaseOrderDetailID | INTEGER | PK, NOT NULL |  | range 1 .. 8845 |
| DueDate | TEXT | NOT NULL | Date the product is expected to be received. | range 2022-04-29T00:00:00 .. 2025-10-21T00:00:00 |
| OrderQty | INTEGER | NOT NULL | Quantity ordered. | values: 3 (4,136), 550 (3,759), 60 (792), 1250 (106), 150 (6), 6000 (4), 1000 (4), 750 (4), 8000 (3), 5000 (3), 2000 (3), 900 (3), 700 (3), 300 (3), 250 (2), 25 (2), 1500 (1), 1050 (1), 630 (1), 600 (1), ... (28 distinct) |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 952 |
| UnitPrice | NUMERIC | NOT NULL | Vendor's selling price of a single unit. | range 0.21 .. 82.8345, avg 34.743 |
| LineTotal | NUMERIC | NOT NULL | Line amount = OrderQty * UnitPrice. | range 37.0755 .. 249420, avg 7212.21 |
| ReceivedQty | NUMERIC | NOT NULL | Quantity actually received from the vendor. | range 2 .. 8000, avg 263.12 |
| RejectedQty | NUMERIC | NOT NULL | Quantity rejected during inspection. | values: 0 (8,282), 82 (203), 55 (127), 550 (74), 3 (58), 9 (37), 27 (18), 6 (17), 60 (15), 125 (5), 1250 (4), 187 (4), 1 (1) |
| StockedQty | NUMERIC | NOT NULL | Quantity accepted into inventory (= ReceivedQty - RejectedQty). | range 0 .. 8000, avg 254.901 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-22T00:00:00 .. 2026-08-11T12:25:46.483000 |

## Relationships

- Purchasing__PurchaseOrderDetail.ProductID = Production__Product.ProductID  [declared]
- Purchasing__PurchaseOrderDetail.PurchaseOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID  [declared]
