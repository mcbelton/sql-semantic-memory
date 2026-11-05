# Production__ProductProductPhoto

**Type:** table | **Domain:** Production | **Rows:** 504 | **SQL name:** `Production__ProductProductPhoto`

Cross-reference mapping products to their photos.

**Primary key:** ProductID, ProductPhotoID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 999 |
| ProductPhotoID | INTEGER | PK, FK -> Production__ProductPhoto.ProductPhotoID, NOT NULL |  | range 1 .. 179 |
| Primary | TEXT | NOT NULL | Whether this is the principal photo (reserved word, quote as "Primary"). | codes: 0=Not the principal image, 1=Principal image; values: '1' (504) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-03-31T00:00:00 .. 2024-04-29T00:00:00 |

## Relationships

- Production__ProductProductPhoto.ProductID = Production__Product.ProductID  [declared]
- Production__ProductProductPhoto.ProductPhotoID = Production__ProductPhoto.ProductPhotoID  [declared]
