# Production__ProductListPriceHistory

**Type:** table | **Domain:** Production | **Rows:** 395 | **SQL name:** `Production__ProductListPriceHistory`

History of product list prices (StartDate/EndDate; EndDate NULL = current).

**Primary key:** ProductID, StartDate

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 707 .. 999 |
| StartDate | TEXT | PK, NOT NULL |  | range 2022-05-30T00:00:00 .. 2024-05-29T00:00:00 |
| EndDate | TEXT |  |  | range 2023-05-29T00:00:00 .. 2024-05-28T00:00:00; 49.37% null |
| ListPrice | NUMERIC | NOT NULL |  | range 2.29 .. 3578.27, avg 747.662 |
| ModifiedDate | TEXT | NOT NULL |  | range 2023-05-29T00:00:00 .. 2024-05-28T00:00:00 |

## Relationships

- Production__ProductListPriceHistory.ProductID = Production__Product.ProductID  [declared]
