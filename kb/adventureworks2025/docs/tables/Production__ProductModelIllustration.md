# Production__ProductModelIllustration

**Type:** table | **Domain:** Production | **Rows:** 7 | **SQL name:** `Production__ProductModelIllustration`

Cross-reference mapping product models to illustrations.

**Primary key:** ProductModelID, IllustrationID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductModelID | INTEGER | PK, FK -> Production__ProductModel.ProductModelID, NOT NULL |  | range 7 .. 67 |
| IllustrationID | INTEGER | PK, FK -> Production__Illustration.IllustrationID, NOT NULL |  | range 3 .. 6 |
| ModifiedDate | TEXT | NOT NULL |  | range 2025-01-08T14:41:02.167000 .. 2025-01-08T14:41:02.200000 |

## Relationships

- Production__ProductModelIllustration.ProductModelID = Production__ProductModel.ProductModelID  [declared]
- Production__ProductModelIllustration.IllustrationID = Production__Illustration.IllustrationID  [declared]
