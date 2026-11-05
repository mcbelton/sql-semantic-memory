# Production__ProductModelProductDescriptionCulture

**Type:** table | **Domain:** Production | **Rows:** 762 | **SQL name:** `Production__ProductModelProductDescriptionCulture`

Cross-reference mapping product models to their descriptions per language (CultureID is space padded, e.g. 'en    ').

**Primary key:** ProductModelID, ProductDescriptionID, CultureID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductModelID | INTEGER | PK, FK -> Production__ProductModel.ProductModelID, NOT NULL |  | range 1 .. 127 |
| ProductDescriptionID | INTEGER | PK, FK -> Production__ProductDescription.ProductDescriptionID, NOT NULL |  | range 3 .. 2010 |
| CultureID | TEXT | PK, FK -> Production__Culture.CultureID, NOT NULL |  | values: 'zh-cht' (127), 'th    ' (127), 'he    ' (127), 'fr    ' (127), 'en    ' (127), 'ar    ' (127) |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-04-29T00:00:00 .. 2024-04-29T00:00:00 |

## Relationships

- Production__ProductModelProductDescriptionCulture.ProductDescriptionID = Production__ProductDescription.ProductDescriptionID  [declared]
- Production__ProductModelProductDescriptionCulture.CultureID = Production__Culture.CultureID  [declared]
- Production__ProductModelProductDescriptionCulture.ProductModelID = Production__ProductModel.ProductModelID  [declared]
