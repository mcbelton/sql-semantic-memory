# Production__Product

**Type:** table | **Domain:** Production | **Rows:** 504 | **SQL name:** `Production__Product`

Products sold or used in manufacturing: bikes, components, clothing and accessories, with pricing, cost, attributes and lifecycle dates.

**Synonyms:** products, items, SKUs, parts, bikes, merchandise

**Primary key:** ProductID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, NOT NULL | Primary key. | range 1 .. 999 |
| Name | TEXT | NOT NULL | Product name. | e.g. 'AWC Logo Cap', 'Adjustable Race', 'All-Purpose Bike Stand'; 504 distinct |
| ProductNumber | TEXT | NOT NULL | Unique product identification number (SKU). | e.g. 'AR-5381', 'BA-8327', 'BB-7421'; 504 distinct |
| MakeFlag | TEXT | NOT NULL | Whether the product is made in-house. | codes: 0=Purchased from a vendor, 1=Manufactured in-house; values: '0' (265), '1' (239) |
| FinishedGoodsFlag | TEXT | NOT NULL | Whether the product is a salable finished good. | codes: 0=Not a salable item (component/raw material), 1=Salable finished good; values: '1' (295), '0' (209) |
| Color | TEXT |  | Product color (NULL for many components). | values: 'Black' (93), 'Silver' (43), 'Red' (38), 'Yellow' (36), 'Blue' (26), 'Multi' (8), 'Silver/Black' (7), 'White' (4), 'Grey' (1); 49.21% null |
| SafetyStockLevel | INTEGER | NOT NULL | Minimum inventory quantity. | values: 500 (167), 1000 (156), 100 (97), 4 (54), 800 (25), 60 (5) |
| ReorderPoint | INTEGER | NOT NULL | Inventory level that triggers a purchase order or work order. | values: 375 (167), 750 (156), 75 (97), 3 (54), 600 (25), 45 (5) |
| StandardCost | NUMERIC | NOT NULL | Standard (current) cost of the product. | range 0 .. 2171.2942, avg 258.603 |
| ListPrice | NUMERIC | NOT NULL | Selling (list) price. | range 0 .. 3578.27, avg 438.666 |
| Size | TEXT |  | Product size (frame size in cm for bikes, or S/M/L/XL for clothing). | values: '44' (29), '48' (25), '52' (16), '58' (15), '42' (15), '38' (12), 'M' (11), 'L' (11), '62' (11), '60' (11), '46' (11), '40' (11), 'S' (9), '54' (9), '50' (9), 'XL' (3), '56' (2), '70' (1); 58.13% null |
| SizeUnitMeasureCode | TEXT | FK -> Production__UnitMeasure.UnitMeasureCode | Unit of measure for Size (padded code, e.g. 'CM '). | values: 'CM ' (176); 65.08% null |
| WeightUnitMeasureCode | TEXT | FK -> Production__UnitMeasure.UnitMeasureCode | Unit of measure for Weight (padded code, e.g. 'LB ', 'G  '). | values: 'LB ' (176), 'G  ' (29); 59.33% null |
| Weight | NUMERIC |  | Product weight. | range 2.12 .. 1050, avg 74.0692; 59.33% null |
| DaysToManufacture | INTEGER | NOT NULL | Number of days required to manufacture the product. | values: 0 (246), 1 (154), 4 (97), 2 (7) |
| ProductLine | TEXT |  | Product line. Values are space padded ('R '): use TRIM(ProductLine) = 'R'. | codes: R=Road, M=Mountain, T=Touring, S=Standard; values: 'R ' (100), 'M ' (91), 'T ' (52), 'S ' (35); 44.84% null |
| Class | TEXT |  | Quality class. Space padded ('H '): use TRIM(Class). | codes: H=High, M=Medium, L=Low; values: 'L ' (97), 'H ' (82), 'M ' (68); 50.99% null |
| Style | TEXT |  | Target style. Space padded ('U '): use TRIM(Style). | codes: W=Womens, M=Mens, U=Universal; values: 'U ' (176), 'W ' (28), 'M ' (7); 58.13% null |
| ProductSubcategoryID | INTEGER | FK -> Production__ProductSubcategory.ProductSubcategoryID | Subcategory. Join Production__ProductSubcategory -> Production__ProductCategory. | range 1 .. 37; 41.47% null |
| ProductModelID | INTEGER | FK -> Production__ProductModel.ProductModelID | Product model. Join Production__ProductModel. | range 1 .. 128; 41.47% null |
| SellStartDate | TEXT | NOT NULL | Date the product became available for sale. | range 2019-04-30T00:00:00 .. 2024-05-29T00:00:00 |
| SellEndDate | TEXT |  | Date the product stopped being available for sale (NULL = still sold). | range 2023-05-29T00:00:00 .. 2024-05-28T00:00:00; 80.56% null |
| DiscontinuedDate | TEXT |  | Date the product was discontinued. | 0 distinct; 100.0% null |
| rowguid | TEXT | NOT NULL |  | e.g. '01A8C3FC-ED52-458E-A634-D5B6E2ACCFED', '01C901E3-4323-48ED-AB9E-9BFDA28BDEF6', '02935111-A546-4C6D-941F-BE12D42C158E'; 504 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2025-02-07T10:01:36.827000 .. 2025-02-07T10:03:55.510000 |

## Relationships

- Production__BillOfMaterials.ProductAssemblyID = Production__Product.ProductID  [declared]
- Production__BillOfMaterials.ComponentID = Production__Product.ProductID  [declared]
- Production__Product.SizeUnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Production__Product.WeightUnitMeasureCode = Production__UnitMeasure.UnitMeasureCode  [declared]
- Production__Product.ProductModelID = Production__ProductModel.ProductModelID  [declared]
- Production__Product.ProductSubcategoryID = Production__ProductSubcategory.ProductSubcategoryID  [declared]
- Production__ProductCostHistory.ProductID = Production__Product.ProductID  [declared]
- Production__ProductDocument.ProductID = Production__Product.ProductID  [declared]
- Production__ProductInventory.ProductID = Production__Product.ProductID  [declared]
- Production__ProductListPriceHistory.ProductID = Production__Product.ProductID  [declared]
- Production__ProductProductPhoto.ProductID = Production__Product.ProductID  [declared]
- Production__ProductReview.ProductID = Production__Product.ProductID  [declared]
- Production__TransactionHistory.ProductID = Production__Product.ProductID  [declared]
- Production__WorkOrder.ProductID = Production__Product.ProductID  [declared]
- Purchasing__ProductVendor.ProductID = Production__Product.ProductID  [declared]
- Purchasing__PurchaseOrderDetail.ProductID = Production__Product.ProductID  [declared]
- Sales__ShoppingCartItem.ProductID = Production__Product.ProductID  [declared]
- Sales__SpecialOfferProduct.ProductID = Production__Product.ProductID  [declared]
- Production__TransactionHistoryArchive.ProductID = Production__Product.ProductID  [inferred]
- Production__WorkOrderRouting.ProductID = Production__Product.ProductID  [inferred]
- Sales__SalesOrderDetail.ProductID = Production__Product.ProductID  [inferred]

**Unique indexes:** Production__Product__AK_Product_Name (Name); Production__Product__AK_Product_ProductNumber (ProductNumber); Production__Product__AK_Product_rowguid (rowguid)

## Business definitions

- **Gross margin**: Approximate: line revenue minus quantity x current standard cost. For period-accurate cost use Production__ProductCostHistory.
- **Product hierarchy**: Production__ProductCategory (Bikes, Components, Clothing, Accessories) -> Production__ProductSubcategory -> Production__Product. Products without a subcategory are internal components.
- **Finished good**: Product with FinishedGoodsFlag = '1'. MakeFlag = '1' means manufactured in-house, '0' purchased.
- **Active product**: Product still for sale: SellEndDate IS NULL and DiscontinuedDate IS NULL.

## Example queries

**Top 10 products by revenue**

```sql
SELECT p.Name AS product, SUM(d.OrderQty) AS units, ROUND(SUM(d.LineTotal), 2) AS revenue
FROM Sales__SalesOrderDetail d
JOIN Production__Product p ON p.ProductID = d.ProductID
GROUP BY p.ProductID, p.Name
ORDER BY revenue DESC
LIMIT 10;
```

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

**Products at or below their reorder point (inventory across all locations)**

```sql
SELECT p.ProductNumber, p.Name, p.ReorderPoint, p.SafetyStockLevel, COALESCE(SUM(i.Quantity), 0) AS on_hand
FROM Production__Product p
LEFT JOIN Production__ProductInventory i ON i.ProductID = p.ProductID
WHERE p.SellEndDate IS NULL AND p.DiscontinuedDate IS NULL
GROUP BY p.ProductID, p.ProductNumber, p.Name, p.ReorderPoint, p.SafetyStockLevel
HAVING COALESCE(SUM(i.Quantity), 0) <= p.ReorderPoint
ORDER BY on_hand;
```

**Full inventory transaction history of one product (current + archive)**

```sql
SELECT t.TransactionDate, t.TransactionType, t.Quantity, t.ActualCost, t.ReferenceOrderID
FROM (
  SELECT ProductID, TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID
  FROM Production__TransactionHistory
  UNION ALL
  SELECT ProductID, TransactionDate, TransactionType, Quantity, ActualCost, ReferenceOrderID
  FROM Production__TransactionHistoryArchive
) t
JOIN Production__Product p ON p.ProductID = t.ProductID
WHERE p.ProductNumber = 'BK-M68B-42'
ORDER BY t.TransactionDate;
```

