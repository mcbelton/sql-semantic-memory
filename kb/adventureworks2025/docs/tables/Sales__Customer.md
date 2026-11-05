# Sales__Customer

**Type:** table | **Domain:** Sales | **Rows:** 19,820 | **SQL name:** `Sales__Customer`

Customers. A customer is either an individual consumer (PersonID set, StoreID NULL) or a reseller store (StoreID set; PersonID is then the store contact, if any).

**Synonyms:** clients, buyers, accounts

**Primary key:** CustomerID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CustomerID | INTEGER | PK, NOT NULL | Primary key. Referenced by Sales__SalesOrderHeader.CustomerID. | range 1 .. 30118 |
| PersonID | INTEGER | FK -> Person__Person.BusinessEntityID | Individual customer or store contact person. Join Person__Person.BusinessEntityID for the name. | range 291 .. 20777; 3.54% null |
| StoreID | INTEGER | FK -> Sales__Store.BusinessEntityID | Reseller store; NULL for individual customers. Join Sales__Store.BusinessEntityID. | range 292 .. 2051; 93.26% null |
| TerritoryID | INTEGER | FK -> Sales__SalesTerritory.TerritoryID | Sales territory where the customer is located. Join Sales__SalesTerritory. | range 1 .. 10 |
| AccountNumber | TEXT | NOT NULL | Customer account number assigned by the accounting system ('AW' + zero-padded CustomerID). | e.g. 'AW00000001', 'AW00000002', 'AW00000003'; 19,820 distinct |
| rowguid | TEXT | NOT NULL |  | e.g. '0006E071-D04E-426D-81CA-D512E229F3E2', '000DC1BD-8B01-41B8-9012-AA3B19DC65C6', '000F058F-7B32-427E-866B-A0D4D3385AC8'; 19,820 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2025-09-11T11:15:07.263000 .. 2025-09-11T11:15:07.263000 |

## Relationships

- Sales__Customer.PersonID = Person__Person.BusinessEntityID  [declared]
- Sales__Customer.StoreID = Sales__Store.BusinessEntityID  [declared]
- Sales__Customer.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesOrderHeader.CustomerID = Sales__Customer.CustomerID  [declared]

**Unique indexes:** Sales__Customer__AK_Customer_AccountNumber (AccountNumber); Sales__Customer__AK_Customer_rowguid (rowguid)

## Business definitions

- **Individual customer**: A Sales__Customer with PersonID set and StoreID NULL (Person__Person.PersonType = 'IN'). Buys online (OnlineOrderFlag = '1').
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

