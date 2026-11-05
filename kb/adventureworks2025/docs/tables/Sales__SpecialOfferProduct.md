# Sales__SpecialOfferProduct

**Type:** table | **Domain:** Sales | **Rows:** 538 | **SQL name:** `Sales__SpecialOfferProduct`

Cross-reference of which products are eligible for which special offers.

**Primary key:** SpecialOfferID, ProductID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SpecialOfferID | INTEGER | PK, FK -> Sales__SpecialOffer.SpecialOfferID, NOT NULL |  | range 1 .. 16 |
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 680 .. 999 |
| rowguid | TEXT | NOT NULL |  | e.g. '0020931C-087C-42F8-B441-EBE3D3B5F51E', '00365938-3422-494E-B92E-C00AFD691469', '005D8818-0E25-4770-9A86-2B05371A5A1B'; 538 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-03-31T00:00:00 .. 2025-02-28T00:00:00 |

## Relationships

- Sales__SalesOrderDetail.SpecialOfferID = Sales__SpecialOfferProduct.SpecialOfferID AND Sales__SalesOrderDetail.ProductID = Sales__SpecialOfferProduct.ProductID  [declared]
- Sales__SpecialOfferProduct.ProductID = Production__Product.ProductID  [declared]
- Sales__SpecialOfferProduct.SpecialOfferID = Sales__SpecialOffer.SpecialOfferID  [declared]

**Unique indexes:** Sales__SpecialOfferProduct__AK_SpecialOfferProduct_rowguid (rowguid)
