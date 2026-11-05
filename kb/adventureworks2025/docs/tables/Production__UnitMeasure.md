# Production__UnitMeasure

**Type:** table | **Domain:** Production | **Rows:** 38 | **SQL name:** `Production__UnitMeasure`

Unit of measure lookup. Codes are space padded to 3 characters ('EA ', 'LB ', 'CM ').

**Primary key:** UnitMeasureCode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| UnitMeasureCode | TEXT | PK, NOT NULL |  | e.g. 'BOX', 'BTL', 'C  ' (38 distinct) |
| Name | TEXT | NOT NULL |  | e.g. 'Bottle', 'Boxes', 'Canister' (38 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__BillOfMaterials.UnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Production__Product.SizeUnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Production__Product.WeightUnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Purchasing__ProductVendor.UnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]

**Unique indexes:** Production__UnitMeasure__AK_UnitMeasure_Name (Name)
