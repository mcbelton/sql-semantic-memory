# Sales__SalesOrderHeader

**Type:** table | **Domain:** Sales | **Rows:** 31,465 | **SQL name:** `Sales__SalesOrderHeader`

General sales order information: one row per customer order, with dates, customer, channel, sales person, territory, addresses, payment and order totals.

**Grain:** one row per sales order (SalesOrderID)

**Synonyms:** sales orders, orders, sales, invoices, order header

**Notes:**
- Net sales revenue = SUM(SubTotal) (excludes tax and freight); TotalDue = SubTotal + TaxAmt + Freight.
- OnlineOrderFlag = '1' means an internet order by an individual customer (no SalesPersonID); '0' means a reseller order placed by a sales person.

**Primary key:** SalesOrderID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SalesOrderID | INTEGER | PK, NOT NULL | Primary key of the order. SalesOrderNumber is the same number with an 'SO' prefix. | range 43659 .. 75123 |
| RevisionNumber | INTEGER | NOT NULL | Incremental number tracking changes to the order over time. | values: 10 (31,435), 11 (30) |
| OrderDate | TEXT | NOT NULL | Date the order was placed (ISO text). Use for sales period analysis. | range 2022-05-30T00:00:00 .. 2025-06-29T00:00:00 |
| DueDate | TEXT | NOT NULL | Date the order is due to the customer. | range 2022-06-11T00:00:00 .. 2025-07-11T00:00:00 |
| ShipDate | TEXT |  | Date the order was shipped. | range 2022-06-06T00:00:00 .. 2025-07-06T00:00:00 |
| Status | INTEGER | NOT NULL | Order current status. | codes: 1=In process, 2=Approved, 3=Backordered, 4=Rejected, 5=Shipped, 6=Cancelled; values: 5 (31,465) |
| OnlineOrderFlag | TEXT | NOT NULL | Sales channel flag. | codes: 0=Order placed by a sales person (reseller channel), 1=Order placed online by the customer (internet channel); values: '1' (27,659), '0' (3,806) |
| SalesOrderNumber | TEXT | NOT NULL | Unique sales order identification number ('SO' + SalesOrderID). | e.g. 'SO43659', 'SO43660', 'SO43661'; 31,465 distinct |
| PurchaseOrderNumber | TEXT |  | Customer purchase order number reference (reseller orders only). | e.g. 'PO522145787', 'PO18850127500', 'PO18473189620'; 3,806 distinct; 87.9% null |
| AccountNumber | TEXT |  | Financial accounting number reference. | e.g. '10-4020-000676', '10-4020-000117', '10-4020-000442'; 19,119 distinct |
| CustomerID | INTEGER | FK -> Sales__Customer.CustomerID, NOT NULL | Customer who placed the order. Join Sales__Customer. | range 11000 .. 30118 |
| SalesPersonID | INTEGER | FK -> Sales__SalesPerson.BusinessEntityID | Sales person who created the order (NULL for online orders). Join Sales__SalesPerson / Person__Person on BusinessEntityID. | range 274 .. 290; 87.9% null |
| TerritoryID | INTEGER | FK -> Sales__SalesTerritory.TerritoryID | Sales territory in which the sale was made. Join Sales__SalesTerritory. | range 1 .. 10 |
| BillToAddressID | INTEGER | FK -> Person__Address.AddressID, NOT NULL | Customer billing address. Join Person__Address. | range 405 .. 29883 |
| ShipToAddressID | INTEGER | FK -> Person__Address.AddressID, NOT NULL | Customer shipping address. Join Person__Address -> Person__StateProvince -> Person__CountryRegion for geography. | range 9 .. 29883 |
| ShipMethodID | INTEGER | FK -> Purchasing__ShipMethod.ShipMethodID, NOT NULL | Shipping method. Join Purchasing__ShipMethod. | range 1 .. 5 |
| CreditCardID | INTEGER | FK -> Sales__CreditCard.CreditCardID | Credit card used for payment. Join Sales__CreditCard. | range 1 .. 19237; 3.59% null |
| CreditCardApprovalCode | TEXT |  | Approval code provided by the credit card company. | e.g. '105041Vi84182', '115213Vi29411', '85274Vi6854'; 30,334 distinct; 3.59% null |
| CurrencyRateID | INTEGER | FK -> Sales__CurrencyRate.CurrencyRateID | Currency exchange rate used (NULL = US dollars). Join Sales__CurrencyRate. | range 2 .. 12431; 55.58% null |
| SubTotal | NUMERIC | NOT NULL | Net sales amount of the order = SUM(Sales__SalesOrderDetail.LineTotal). The standard revenue measure. | range 1.374 .. 163930.3943, avg 3491.07 |
| TaxAmt | NUMERIC | NOT NULL | Tax amount. | range 0.1099 .. 17948.5186, avg 323.756 |
| Freight | NUMERIC | NOT NULL | Shipping cost charged. | range 0.0344 .. 5608.9121, avg 101.174 |
| TotalDue | NUMERIC | NOT NULL | Total due from the customer = SubTotal + TaxAmt + Freight (gross billed amount). | range 1.5183 .. 187487.825, avg 3916 |
| Comment | TEXT |  | Sales representative comments (always NULL in this data). | 0 distinct; 100.0% null |
| rowguid | TEXT | NOT NULL |  | e.g. '0000DE87-AB3F-4920-AC46-C404834241A0', '00032DF7-5D34-4ECC-9BC2-353D3C918E93', '0004E1D8-4756-4CBE-9F38-C1D8B3E47130'; 31,465 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-06-06T00:00:00 .. 2025-07-06T00:00:00 |

## Relationships

- Sales__SalesOrderDetail.SalesOrderID = Sales__SalesOrderHeader.SalesOrderID  [declared]
- Sales__SalesOrderHeader.BillToAddressID = Person__Address.AddressID  [declared]
- Sales__SalesOrderHeader.ShipToAddressID = Person__Address.AddressID  [declared]
- Sales__SalesOrderHeader.CreditCardID = Sales__CreditCard.CreditCardID  [declared]
- Sales__SalesOrderHeader.CurrencyRateID = Sales__CurrencyRate.CurrencyRateID  [declared]
- Sales__SalesOrderHeader.CustomerID = Sales__Customer.CustomerID  [declared]
- Sales__SalesOrderHeader.SalesPersonID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__SalesOrderHeader.ShipMethodID = Purchasing__ShipMethod.ShipMethodID  [declared]
- Sales__SalesOrderHeader.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesOrderHeaderSalesReason.SalesOrderID = Sales__SalesOrderHeader.SalesOrderID  [declared]
- Sales__SalesOrderHeader.SalesPersonID = Person__Person.BusinessEntityID  [curated; Name of the sales person who took the order.]
- Production__TransactionHistory.ReferenceOrderID = Sales__SalesOrderHeader.SalesOrderID AND (Production__TransactionHistory.TransactionType = 'S')  [curated; Sales order behind a sales transaction.]
- Production__TransactionHistoryArchive.ReferenceOrderID = Sales__SalesOrderHeader.SalesOrderID AND (Production__TransactionHistoryArchive.TransactionType = 'S')  [kg; Archived Inventory Transaction for sales order Sales Order]

**Unique indexes:** Sales__SalesOrderHeader__AK_SalesOrderHeader_SalesOrderNumber (SalesOrderNumber); Sales__SalesOrderHeader__AK_SalesOrderHeader_rowguid (rowguid)

## Business definitions

- **Sales revenue**: Net sales excluding tax and freight. Order level: SUM(SubTotal). Line level (by product): SUM(LineTotal) - both give the same total.
- **Gross billed amount**: Amount invoiced to customers including tax and freight.
- **Order count**: Number of sales orders.
- **Average order value**: Net sales revenue divided by number of orders.
- **Sales channel**: Online/internet channel = OnlineOrderFlag = '1' (individual customers, no sales person). Reseller channel = OnlineOrderFlag = '0' (stores, with SalesPersonID).

## Example queries

**Net sales revenue and order count by year**

```sql
SELECT substr(OrderDate, 1, 4) AS order_year, COUNT(*) AS orders, ROUND(SUM(SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader
GROUP BY order_year
ORDER BY order_year;
```

**Monthly order count and revenue trend**

```sql
SELECT substr(OrderDate, 1, 7) AS month, COUNT(*) AS orders, ROUND(SUM(SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader
GROUP BY month
ORDER BY month;
```

**Revenue by sales territory in 2024**

```sql
SELECT st.Name AS territory, st."Group" AS region, ROUND(SUM(soh.SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader soh
JOIN Sales__SalesTerritory st ON st.TerritoryID = soh.TerritoryID
WHERE soh.OrderDate >= '2024-01-01' AND soh.OrderDate < '2025-01-01'
GROUP BY st.Name, st."Group"
ORDER BY revenue DESC;
```

**Online vs reseller sales by year**

```sql
SELECT substr(OrderDate, 1, 4) AS order_year,
       CASE OnlineOrderFlag WHEN '1' THEN 'Online' ELSE 'Reseller' END AS channel,
       COUNT(*) AS orders, ROUND(SUM(SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader
GROUP BY order_year, channel
ORDER BY order_year, channel;
```

**Top 10 resellers (stores) by revenue**

```sql
SELECT s.Name AS store, COUNT(*) AS orders, ROUND(SUM(soh.SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader soh
JOIN Sales__Customer c ON c.CustomerID = soh.CustomerID
JOIN Sales__Store s ON s.BusinessEntityID = c.StoreID
GROUP BY s.BusinessEntityID, s.Name
ORDER BY revenue DESC
LIMIT 10;
```

**Top 10 individual customers by revenue**

```sql
SELECT p.FirstName || ' ' || p.LastName AS customer, COUNT(*) AS orders, ROUND(SUM(soh.SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader soh
JOIN Sales__Customer c ON c.CustomerID = soh.CustomerID
JOIN Person__Person p ON p.BusinessEntityID = c.PersonID
WHERE c.StoreID IS NULL
GROUP BY c.CustomerID, customer
ORDER BY revenue DESC
LIMIT 10;
```

**Revenue by ship-to country**

```sql
SELECT cr.Name AS country, ROUND(SUM(soh.SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader soh
JOIN Person__Address a ON a.AddressID = soh.ShipToAddressID
JOIN Person__StateProvince sp ON sp.StateProvinceID = a.StateProvinceID
JOIN Person__CountryRegion cr ON cr.CountryRegionCode = sp.CountryRegionCode
GROUP BY cr.Name
ORDER BY revenue DESC;
```

