# Purchasing__ProductVendor

**Type:** table | **Domain:** Purchasing | **Rows:** 460 | **SQL name:** `Purchasing__ProductVendor`

Which vendors supply which products, with lead time, prices and order quantity limits.

**Primary key:** ProductID, BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 952 |
| BusinessEntityID | INTEGER | PK, FK -> Purchasing__Vendor.BusinessEntityID, NOT NULL |  | range 1492 .. 1698 |
| AverageLeadTime | INTEGER | NOT NULL | Average days between placing an order with the vendor and receiving the product. | values: 17 (109), 19 (101), 16 (88), 15 (85), 18 (26), 45 (19), 25 (10), 30 (8), 60 (7), 35 (3), 12 (2), 120 (1), 10 (1) |
| StandardPrice | NUMERIC | NOT NULL | Vendor's usual selling price. | range 0.2 .. 78.89, avg 34.6765 |
| LastReceiptCost | NUMERIC |  | Price paid on the last purchase. | range 0.21 .. 82.8345, avg 36.2759 |
| LastReceiptDate | TEXT |  | Date the product was last received. | range 2022-07-21T00:00:00 .. 2025-10-21T00:00:00 |
| MinOrderQty | INTEGER | NOT NULL | Minimum quantity that should be ordered. | values: 1 (285), 100 (111), 20 (20), 500 (18), 5000 (7), 1000 (6), 150 (4), 1500 (3), 50 (3), 4 (2), 75 (1) |
| MaxOrderQty | INTEGER | NOT NULL | Maximum quantity that should be ordered. | values: 5 (285), 1000 (104), 100 (20), 500 (11), 5000 (9), 10000 (7), 7500 (6), 15000 (3), 8000 (3), 2500 (3), 200 (3), 2000 (2), 1500 (1), 750 (1), 600 (1), 300 (1) |
| OnOrderQty | INTEGER |  | Quantity currently on order. | values: 3 (63), 300 (34), 60 (7), 150 (6), 6000 (4), 1000 (4), 750 (4), 8000 (3), 5000 (3), 2000 (3), 1250 (3), 900 (3), 700 (3), 250 (2), 25 (2), 1500 (1), 1050 (1), 630 (1), 600 (1), 500 (1), ... (26 distinct); 66.3% null |
| UnitMeasureCode | TEXT | FK -> Production__UnitMeasure.UnitMeasureCode, NOT NULL | Unit of measure (padded code, e.g. 'EA ', 'CTN'). | values: 'CTN' (178), 'EA ' (154), 'CAN' (68), 'CS ' (38), 'GAL' (10), 'DZ ' (7), 'PAK' (5) |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-07-21T00:00:00 .. 2026-08-11T12:20:28.343000 |

## Relationships

- Purchasing__ProductVendor.ProductID = Production__Product.ProductID  [declared]
- Purchasing__ProductVendor.UnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Purchasing__ProductVendor.BusinessEntityID = Purchasing__Vendor.BusinessEntityID  [declared]
