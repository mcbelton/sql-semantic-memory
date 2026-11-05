# Production__ProductDescription

**Type:** table | **Domain:** Production | **Rows:** 762 | **SQL name:** `Production__ProductDescription`

Product descriptions (marketing text) in several languages.

**Primary key:** ProductDescriptionID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductDescriptionID | INTEGER | PK, NOT NULL |  | range 3 .. 2010 |
| Description | TEXT | NOT NULL |  | e.g. 'Chromoly steel.', 'Aluminum alloy cups; large diameter spindle.', 'Aluminum alloy cups and a hollow axle.'; 733 distinct |
| rowguid | TEXT | NOT NULL |  | e.g. '00FFDFAC-0207-4DF0-8051-7D3C884816F3', '016CBBE9-D51B-4A50-94CD-5FF2DA577C5B', '01FC4BEE-5EE9-4B2A-A5C3-EABA6036A705'; 762 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-04-29T00:00:00 .. 2025-02-07T10:32:17.973000 |

## Relationships

- Production__ProductModelProductDescriptionCulture.ProductDescriptionID = Production__ProductDescription.ProductDescriptionID  [declared]

**Unique indexes:** Production__ProductDescription__AK_ProductDescription_rowguid (rowguid)
