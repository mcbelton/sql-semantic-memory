# Production__ProductCostHistory

**Type:** table | **Domain:** Production | **Rows:** 395 | **SQL name:** `Production__ProductCostHistory`

History of product standard costs (StartDate/EndDate; EndDate NULL = current). Use for period-accurate cost of goods.

**Primary key:** ProductID, StartDate

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 707 .. 999 |
| StartDate | TEXT | PK, NOT NULL |  | range 2022-05-30T00:00:00 .. 2024-05-29T00:00:00 |
| EndDate | TEXT |  |  | range 2023-05-29T00:00:00 .. 2024-05-28T00:00:00; 49.37% null |
| StandardCost | NUMERIC | NOT NULL |  | range 0.8565 .. 2171.2942, avg 434.266 |
| ModifiedDate | TEXT | NOT NULL |  | range 2023-05-29T00:00:00 .. 2024-05-28T00:00:00 |

## Relationships

- Production__ProductCostHistory.ProductID = Production__Product.ProductID  [declared]
