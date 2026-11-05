# Sales__Store

**Type:** table | **Domain:** Sales | **Rows:** 701 | **SQL name:** `Sales__Store`

Reseller customers: bike shops that buy Adventure Works products for resale.

**Synonyms:** resellers, stores, shops, dealers, retailers, B2B customers

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__BusinessEntity.BusinessEntityID, NOT NULL | Primary key (business entity of the store). Referenced by Sales__Customer.StoreID. | range 292 .. 2051 |
| Name | TEXT | NOT NULL | Store (company) name. | e.g. 'Next-Door Bike Store', 'Professional Sales and Service', 'Riders Company'; 699 distinct |
| SalesPersonID | INTEGER | FK -> Sales__SalesPerson.BusinessEntityID | Sales person assigned to the store. Join Sales__SalesPerson. | range 275 .. 290 |
| Demographics | TEXT |  | XML survey data about the store: annual sales, revenue, business type, specialty, square feet, number of employees. | e.g. '<StoreSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/StoreSurvey"><AnnualSales>1000000<...', '<StoreSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/StoreSurvey"><AnnualSales>1000000<...', '<StoreSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/StoreSurvey"><AnnualSales>1000000<...'; 701 distinct |
| rowguid | TEXT | NOT NULL |  | e.g. '004EA91C-FCD4-4973-87EF-9059C6E20BB5', '00A7E190-D705-4791-AAB5-AD218497DD06', '00E69DB8-5933-4F61-A963-7808C4BAF0C5'; 701 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2025-09-11T11:15:07.497000 .. 2025-09-11T11:15:07.497000 |

## Relationships

- Sales__Customer.StoreID = Sales__Store.BusinessEntityID  [declared]
- Sales__Store.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Sales__Store.SalesPersonID = Sales__SalesPerson.BusinessEntityID  [declared]

**Unique indexes:** Sales__Store__AK_Store_rowguid (rowguid)

## Business definitions

- **Reseller**: A Sales__Customer with StoreID set; the store name is Sales__Store.Name. Reseller orders are placed by a sales person (OnlineOrderFlag = '0').

## Example queries

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

