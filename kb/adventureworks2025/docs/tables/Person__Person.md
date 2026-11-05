# Person__Person

**Type:** table | **Domain:** Person | **Rows:** 19,972 | **SQL name:** `Person__Person`

Every human known to Adventure Works: employees, sales people, individual customers, store and vendor contacts. Holds names and contact preferences.

**Synonyms:** people, persons, contacts, names, individuals

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__BusinessEntity.BusinessEntityID, NOT NULL | Primary key; same id used by HumanResources__Employee, Sales__SalesPerson and Sales__Customer.PersonID. | range 1 .. 20777 |
| PersonType | TEXT | NOT NULL | Primary role of the person. | codes: SC=Store contact, IN=Individual (retail) customer, SP=Sales person, EM=Employee (non-sales), VC=Vendor contact, GC=General contact; values: 'IN' (18,484), 'SC' (753), 'GC' (289), 'EM' (273), 'VC' (156), 'SP' (17) |
| NameStyle | TEXT | NOT NULL | Name order. | codes: 0=Western style (first name, last name), 1=Eastern style (last name, first name); values: '0' (19,972) |
| Title | TEXT |  | Courtesy title (Mr., Ms., ...). | values: 'Mr.' (577), 'Ms.' (415), 'Sr.' (11), 'Sra.' (3), 'Mrs.' (2), 'Ms' (1); 94.95% null |
| FirstName | TEXT | NOT NULL | First name of the person. | sensitive - values not captured |
| MiddleName | TEXT |  | Middle name or initial. | sensitive - values not captured; 42.55% null |
| LastName | TEXT | NOT NULL | Last name of the person. | sensitive - values not captured |
| Suffix | TEXT |  | Surname suffix (Jr., Sr., ...). | values: 'Jr.' (33), 'Sr.' (6), 'II' (6), 'IV' (3), 'III' (3), 'PhD' (2); 99.73% null |
| EmailPromotion | INTEGER | NOT NULL | E-mail marketing consent. | codes: 0=Does not want promotions, 1=Wants promotions from Adventure Works, 2=Wants promotions from Adventure Works and partners; values: 0 (11,158), 1 (5,044), 2 (3,770) |
| AdditionalContactInfo | TEXT |  | Additional contact information in XML. | values: '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...', '<AdditionalContactInfo xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ContactInfo" xmlns:crm="...'; 99.95% null |
| Demographics | TEXT |  | XML survey of individual customers (total purchase, birth date, marital status, yearly income, gender, children, education, occupation, home ownership, cars, commute distance). | e.g. '<IndividualSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/IndividualSurvey"><TotalPurch...', '<IndividualSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/IndividualSurvey"><TotalPurch...', '<IndividualSurvey xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/IndividualSurvey"><TotalPurch...'; 19,115 distinct |
| rowguid | TEXT | NOT NULL |  | e.g. '000191EF-7424-4A5F-AB19-0852B1F0B78D', '00034881-67FA-4CCA-908A-B1D42030979E', '00061FFE-1635-48C6-88DD-FC1E2127B838'; 19,972 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2015-04-15T16:33:33.060000 .. 2025-06-29T00:00:00 |

## Relationships

- HumanResources__Employee.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Person__BusinessEntityContact.PersonID = Person__Person.BusinessEntityID  [declared]
- Person__EmailAddress.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Person__Password.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Person__Person.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Person__PersonPhone.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Sales__Customer.PersonID = Person__Person.BusinessEntityID  [declared]
- Sales__PersonCreditCard.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Sales__SalesPerson.BusinessEntityID = Person__Person.BusinessEntityID  [curated; Sales person name (same BusinessEntityID; shortcut instead of going through HumanResources__Employee).]
- Sales__SalesOrderHeader.SalesPersonID = Person__Person.BusinessEntityID  [curated; Name of the sales person who took the order.]
- Purchasing__PurchaseOrderHeader.EmployeeID = Person__Person.BusinessEntityID  [curated; Name of the employee (buyer) who created the purchase order.]

**Unique indexes:** Person__Person__AK_Person_rowguid (rowguid)

## Business definitions

- **Individual customer**: A Sales__Customer with PersonID set and StoreID NULL (Person__Person.PersonType = 'IN'). Buys online (OnlineOrderFlag = '1').

## Example queries

**Sales people ranked by year-to-date sales with quota attainment**

```sql
SELECT p.FirstName || ' ' || p.LastName AS sales_person, st.Name AS territory,
       ROUND(sp.SalesYTD, 2) AS sales_ytd, sp.SalesQuota,
       ROUND(100.0 * sp.SalesYTD / sp.SalesQuota, 1) AS quota_pct
FROM Sales__SalesPerson sp
JOIN Person__Person p ON p.BusinessEntityID = sp.BusinessEntityID
LEFT JOIN Sales__SalesTerritory st ON st.TerritoryID = sp.TerritoryID
ORDER BY sp.SalesYTD DESC;
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

**Current pay rate of each employee with job title and department**

```sql
WITH latest_pay AS (
  SELECT BusinessEntityID, Rate,
         ROW_NUMBER() OVER (PARTITION BY BusinessEntityID ORDER BY RateChangeDate DESC) AS rn
  FROM HumanResources__EmployeePayHistory
)
SELECT p.FirstName || ' ' || p.LastName AS employee, e.JobTitle, d.Name AS department, lp.Rate AS hourly_rate
FROM HumanResources__Employee e
JOIN Person__Person p ON p.BusinessEntityID = e.BusinessEntityID
JOIN latest_pay lp ON lp.BusinessEntityID = e.BusinessEntityID AND lp.rn = 1
JOIN HumanResources__EmployeeDepartmentHistory edh ON edh.BusinessEntityID = e.BusinessEntityID AND edh.EndDate IS NULL
JOIN HumanResources__Department d ON d.DepartmentID = edh.DepartmentID
ORDER BY lp.Rate DESC;
```

