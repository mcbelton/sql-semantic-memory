# Sales__SalesOrderDetail

**Type:** table | **Domain:** Sales | **Rows:** 121,317 | **SQL name:** `Sales__SalesOrderDetail`

Individual products (order lines) of each sales order: product, quantity, unit price, discount and line total.

**Grain:** one row per order line (SalesOrderID, SalesOrderDetailID)

**Synonyms:** order lines, order items, line items, sales lines, products sold

**Primary key:** SalesOrderID, SalesOrderDetailID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SalesOrderID | INTEGER | PK, FK -> Sales__SalesOrderHeader.SalesOrderID, NOT NULL | Order the line belongs to. Join Sales__SalesOrderHeader. | range 43659 .. 75123 |
| SalesOrderDetailID | INTEGER | PK, NOT NULL | Line number, unique across all orders. | range 1 .. 121317 |
| CarrierTrackingNumber | TEXT |  | Shipment tracking number supplied by the shipper (reseller orders). | e.g. '4911-403C-98', '6431-4D57-83', '4E0A-4F89-AE'; 3,806 distinct; 49.79% null |
| OrderQty | INTEGER | NOT NULL | Quantity of the product ordered on this line. | range 1 .. 44, avg 2.26608 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL | Product sold. Join Production__Product. | range 707 .. 999 |
| SpecialOfferID | INTEGER | FK -> Sales__SpecialOffer.SpecialOfferID, NOT NULL | Promotion applied. Join Sales__SpecialOffer (1 = No Discount). | range 1 .. 16 |
| UnitPrice | NUMERIC | NOT NULL | Selling price of a single unit. | range 1.3282 .. 3578.27, avg 465.093 |
| UnitPriceDiscount | NUMERIC | NOT NULL | Discount as a fraction of the unit price (0.15 = 15% off). | values: 0 (118,035), 0.02 (1,310), 0.05 (606), 0.15 (590), 0.2 (231), 0.1 (178), 0.4 (169), 0.35 (137), 0.3 (61) |
| LineTotal | NUMERIC | NOT NULL | Line amount = UnitPrice * (1 - UnitPriceDiscount) * OrderQty. | range 1.374 .. 27893.619, avg 905.449 |
| rowguid | TEXT | NOT NULL |  | e.g. '0000C99C-2B71-4885-B976-C1CCAE896EF2', '00010EA0-5D0F-4F0A-A3FB-8FE8A8210956', '00015BA1-153F-490E-8D59-4127F02B72E8'; 121,317 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-05-30T00:00:00 .. 2025-06-29T00:00:00 |

## Relationships

- Sales__SalesOrderDetail.SalesOrderID = Sales__SalesOrderHeader.SalesOrderID  [declared]
- Sales__SalesOrderDetail.SpecialOfferID = Sales__SpecialOfferProduct.SpecialOfferID AND Sales__SalesOrderDetail.ProductID = Sales__SpecialOfferProduct.ProductID  [declared]
- Sales__SalesOrderDetail.ProductID = Production__Product.ProductID  [inferred]
- Sales__SalesOrderDetail.SpecialOfferID = Sales__SpecialOffer.SpecialOfferID  [inferred]

**Unique indexes:** Sales__SalesOrderDetail__AK_SalesOrderDetail_rowguid (rowguid)

## Business definitions

- **Sales revenue**: Net sales excluding tax and freight. Order level: SUM(SubTotal). Line level (by product): SUM(LineTotal) - both give the same total.
- **Units sold**: Number of product units sold.
- **Discount amount**: Value of price discounts granted on order lines.
- **Gross margin**: Approximate: line revenue minus quantity x current standard cost. For period-accurate cost use Production__ProductCostHistory.

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

**Discount amount and revenue by special offer**

```sql
SELECT so.Description AS offer, so.Type, so.Category, COUNT(*) AS order_lines,
       ROUND(SUM(d.OrderQty * d.UnitPrice * d.UnitPriceDiscount), 2) AS discount_amount,
       ROUND(SUM(d.LineTotal), 2) AS revenue
FROM Sales__SalesOrderDetail d
JOIN Sales__SpecialOffer so ON so.SpecialOfferID = d.SpecialOfferID
GROUP BY so.SpecialOfferID, so.Description, so.Type, so.Category
ORDER BY discount_amount DESC;
```

