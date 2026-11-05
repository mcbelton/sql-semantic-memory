# Production__ProductDocument

**Type:** table | **Domain:** Production | **Rows:** 32 | **SQL name:** `Production__ProductDocument`

Cross-reference mapping products to related documents.

**Primary key:** ProductID, DocumentNode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 317 .. 999 |
| DocumentNode | BLOB | PK, FK -> Production__Document.DocumentNode, NOT NULL |  |  |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-12-28T13:51:58.103000 .. 2024-12-28T13:51:58.120000 |

## Relationships

- Production__ProductDocument.ProductID = Production__Product.ProductID  [declared]
- Production__ProductDocument.DocumentNode = Production__Document.DocumentNode  [declared]
