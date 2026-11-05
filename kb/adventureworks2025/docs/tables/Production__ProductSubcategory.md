# Production__ProductSubcategory

**Type:** table | **Domain:** Production | **Rows:** 37 | **SQL name:** `Production__ProductSubcategory`

Second level of the product hierarchy (e.g. Mountain Bikes, Road Bikes, Helmets, Jerseys). Each belongs to one ProductCategory.

**Synonyms:** subcategories, product types

**Primary key:** ProductSubcategoryID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductSubcategoryID | INTEGER | PK, NOT NULL |  | range 1 .. 37 |
| ProductCategoryID | INTEGER | FK -> Production__ProductCategory.ProductCategoryID, NOT NULL |  | range 1 .. 4 |
| Name | TEXT | NOT NULL |  | e.g. 'Bib-Shorts', 'Bike Racks', 'Bike Stands' (37 distinct) |
| rowguid | TEXT | NOT NULL |  | e.g. '000310C0-BCC8-42C4-B0C3-45AE611AF06B', '02C5061D-ECDC-4274-B5F1-E91D76BC3F37', '049FFFA3-9D30-46DF-82F7-F20730EC02B3' (37 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__Product.ProductSubcategoryID = Production__ProductSubcategory.ProductSubcategoryID  [declared]
- Production__ProductSubcategory.ProductCategoryID = Production__ProductCategory.ProductCategoryID  [declared]

**Unique indexes:** Production__ProductSubcategory__AK_ProductSubcategory_Name (Name); Production__ProductSubcategory__AK_ProductSubcategory_rowguid (rowguid)

## Business definitions

- **Product hierarchy**: Production__ProductCategory (Bikes, Components, Clothing, Accessories) -> Production__ProductSubcategory -> Production__Product. Products without a subcategory are internal components.

## Example queries

**Revenue by product category and subcategory**

```sql
SELECT pc.Name AS category, ps.Name AS subcategory, ROUND(SUM(d.LineTotal), 2) AS revenue
FROM Sales__SalesOrderDetail d
JOIN Production__Product p ON p.ProductID = d.ProductID
JOIN Production__ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
JOIN Production__ProductCategory pc ON pc.ProductCategoryID = ps.ProductCategoryID
GROUP BY pc.Name, ps.Name
ORDER BY revenue DESC;
```

**Gross margin by product category (approximate, current standard cost)**

```sql
SELECT pc.Name AS category, ROUND(SUM(d.LineTotal), 2) AS revenue,
       ROUND(SUM(d.OrderQty * p.StandardCost), 2) AS cost,
       ROUND(SUM(d.LineTotal) - SUM(d.OrderQty * p.StandardCost), 2) AS gross_margin
FROM Sales__SalesOrderDetail d
JOIN Production__Product p ON p.ProductID = d.ProductID
JOIN Production__ProductSubcategory ps ON ps.ProductSubcategoryID = p.ProductSubcategoryID
JOIN Production__ProductCategory pc ON pc.ProductCategoryID = ps.ProductCategoryID
GROUP BY pc.Name
ORDER BY gross_margin DESC;
```

