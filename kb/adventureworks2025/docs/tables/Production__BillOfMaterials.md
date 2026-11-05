# Production__BillOfMaterials

**Type:** table | **Domain:** Production | **Rows:** 2,679 | **SQL name:** `Production__BillOfMaterials`

Bill of materials: components required to build each product assembly (hierarchical parent/child).

**Synonyms:** BOM, components list, parts list

**Primary key:** BillOfMaterialsID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BillOfMaterialsID | INTEGER | PK, NOT NULL |  | range 1 .. 3482 |
| ProductAssemblyID | INTEGER | FK -> Production__Product.ProductID | Parent product (assembly). Join Production__Product. | range 3 .. 999; 3.84% null |
| ComponentID | INTEGER | FK -> Production__Product.ProductID, NOT NULL | Component product. Join Production__Product. | range 1 .. 999 |
| StartDate | TEXT | NOT NULL |  | range 2021-03-03T00:00:00 .. 2021-12-22T00:00:00 |
| EndDate | TEXT |  | Date the component stopped being used in the assembly (NULL = current). | range 2021-05-02T00:00:00 .. 2021-11-13T00:00:00; 92.57% null |
| UnitMeasureCode | TEXT | FK -> Production__UnitMeasure.UnitMeasureCode, NOT NULL |  | values: 'EA ' (2,578), 'OZ ' (92), 'IN ' (9) |
| BOMLevel | INTEGER | NOT NULL | Depth of the component from its top-level assembly (0 = top). | values: 1 (1,548), 2 (993), 0 (103), 3 (31), 4 (4) |
| PerAssemblyQty | NUMERIC | NOT NULL | Quantity of the component needed per assembly. | values: 1 (2,080), 2 (343), 4 (88), 8 (81), 36 (28), 3 (27), 9 (14), 40 (8), 10 (4), 37 (3), 5 (2), 41 (1) |
| ModifiedDate | TEXT | NOT NULL |  | range 2021-02-17T00:00:00 .. 2021-12-08T00:00:00 |

## Relationships

- Production__BillOfMaterials.ProductAssemblyID = Production__Product.ProductID  [declared]
- Production__BillOfMaterials.ComponentID = Production__Product.ProductID  [declared]
- Production__BillOfMaterials.UnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]

**Unique indexes:** Production__BillOfMaterials__AK_BillOfMaterials_ProductAssemblyID_ComponentID_StartDate (ProductAssemblyID, ComponentID, StartDate)
