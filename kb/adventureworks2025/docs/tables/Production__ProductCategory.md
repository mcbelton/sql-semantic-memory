# Production__ProductCategory

**Type:** table | **Domain:** Production | **Rows:** 4 | **SQL name:** `Production__ProductCategory`

Top level of the product hierarchy: Bikes, Components, Clothing, Accessories.

**Synonyms:** categories, product categories, product lines

**Primary key:** ProductCategoryID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductCategoryID | INTEGER | PK, NOT NULL |  | range 1 .. 4 |
| Name | TEXT | NOT NULL |  | values: 'Accessories', 'Bikes', 'Clothing', 'Components' |
| rowguid | TEXT | NOT NULL |  | values: '10A7C342-CA82-48D4-8A38-46A2EB089B74', '2BE3BE36-D9A2-4EEE-B593-ED895D97C2A6', 'C657828D-D808-4ABA-91A3-AF2CE02300E9', 'CFBDA25C-DF71-47A7-B81B-64EE161AA37C' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__ProductSubcategory.ProductCategoryID = Production__ProductCategory.ProductCategoryID  [declared]

**Unique indexes:** Production__ProductCategory__AK_ProductCategory_Name (Name); Production__ProductCategory__AK_ProductCategory_rowguid (rowguid)

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

