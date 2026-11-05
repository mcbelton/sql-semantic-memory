# Purchasing__PurchaseOrderHeader

**Type:** table | **Domain:** Purchasing | **Rows:** 4,012 | **SQL name:** `Purchasing__PurchaseOrderHeader`

Purchase orders to vendors: vendor, employee who created it, status, dates, shipping and totals.

**Grain:** one row per purchase order

**Synonyms:** purchase orders, POs, procurement, purchases

**Primary key:** PurchaseOrderID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| PurchaseOrderID | INTEGER | PK, NOT NULL |  | range 1 .. 4012 |
| RevisionNumber | INTEGER | NOT NULL |  | values: 5 (3,813), 6 (130), 7 (43), 8 (15), 10 (4), 9 (3), 21 (1), 15 (1), 13 (1), 11 (1) |
| Status | INTEGER | NOT NULL | Purchase order status. | codes: 1=Pending, 2=Approved, 3=Rejected, 4=Complete; values: 4 (3,689), 1 (225), 3 (86), 2 (12) |
| EmployeeID | INTEGER | FK -> HumanResources__Employee.BusinessEntityID, NOT NULL | Employee who created the purchase order. Join HumanResources__Employee / Person__Person on BusinessEntityID. | range 250 .. 261 |
| VendorID | INTEGER | FK -> Purchasing__Vendor.BusinessEntityID, NOT NULL | Vendor the order was placed with. Join Purchasing__Vendor.BusinessEntityID. | range 1492 .. 1698 |
| ShipMethodID | INTEGER | FK -> Purchasing__ShipMethod.ShipMethodID, NOT NULL | Shipping method. Join Purchasing__ShipMethod. | range 1 .. 5 |
| OrderDate | TEXT | NOT NULL | Purchase order creation date. | range 2022-04-15T00:00:00 .. 2025-09-21T00:00:00 |
| ShipDate | TEXT |  | Estimated shipment date from the vendor. | range 2022-04-24T00:00:00 .. 2025-10-16T00:00:00 |
| SubTotal | NUMERIC | NOT NULL | Purchase amount = SUM(Purchasing__PurchaseOrderDetail.LineTotal). | range 37.0755 .. 997680, avg 15900.3 |
| TaxAmt | NUMERIC | NOT NULL | Tax amount. | range 2.966 .. 79814.4, avg 1272.02 |
| Freight | NUMERIC | NOT NULL | Shipping cost. | range 0.9269 .. 19953.6, avg 394.81 |
| TotalDue | NUMERIC | NOT NULL | Total due to the vendor = SubTotal + TaxAmt + Freight. | range 40.9684 .. 1097448, avg 17567.1 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-24T00:00:00 .. 2026-08-11T12:25:46.483000 |

## Relationships

- Purchasing__PurchaseOrderDetail.PurchaseOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID  [declared]
- Purchasing__PurchaseOrderHeader.EmployeeID = HumanResources__Employee.BusinessEntityID  [declared]
- Purchasing__PurchaseOrderHeader.VendorID = Purchasing__Vendor.BusinessEntityID  [declared]
- Purchasing__PurchaseOrderHeader.ShipMethodID = Purchasing__ShipMethod.ShipMethodID  [declared]
- Purchasing__PurchaseOrderHeader.EmployeeID = Person__Person.BusinessEntityID  [curated; Name of the employee (buyer) who created the purchase order.]
- Production__TransactionHistory.ReferenceOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID AND (Production__TransactionHistory.TransactionType = 'P')  [curated; Purchase order behind a purchase transaction.]
- Production__TransactionHistoryArchive.ReferenceOrderID = Purchasing__PurchaseOrderHeader.PurchaseOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'P')  [kg; Archived Inventory Transaction for purchase order Purchase Order]

## Business definitions

- **Purchase spend**: Amount ordered from vendors excluding tax and freight; usually exclude rejected orders (Status = 3).

## Example queries

**Top 10 vendors by purchase spend**

```sql
SELECT v.Name AS vendor, COUNT(*) AS purchase_orders, ROUND(SUM(poh.SubTotal), 2) AS spend
FROM Purchasing__PurchaseOrderHeader poh
JOIN Purchasing__Vendor v ON v.BusinessEntityID = poh.VendorID
WHERE poh.Status <> 3
GROUP BY v.BusinessEntityID, v.Name
ORDER BY spend DESC
LIMIT 10;
```

