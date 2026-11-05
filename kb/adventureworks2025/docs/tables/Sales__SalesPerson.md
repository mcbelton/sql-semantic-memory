# Sales__SalesPerson

**Type:** table | **Domain:** Sales | **Rows:** 17 | **SQL name:** `Sales__SalesPerson`

Sales representatives (employees) with their territory, quota, bonus, commission and year-to-date sales. Names are in Person__Person (same BusinessEntityID).

**Synonyms:** sales reps, sales representatives, account managers, sellers

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> HumanResources__Employee.BusinessEntityID, NOT NULL | Primary key; same id as HumanResources__Employee and Person__Person. | range 274 .. 290 |
| TerritoryID | INTEGER | FK -> Sales__SalesTerritory.TerritoryID | Territory currently assigned. Join Sales__SalesTerritory (NULL for managers without territory). | range 1 .. 10; 17.65% null |
| SalesQuota | NUMERIC |  | Projected yearly sales (quota). | values: 250000 (11), 300000 (3); 17.65% null |
| Bonus | NUMERIC | NOT NULL | Bonus due if quota is met. | values: 0 (3), 5000 (2), 6700 (1), 5650 (1), 5150 (1), 4100 (1), 3900 (1), 3550 (1), 3500 (1), 2500 (1), 2000 (1), 985 (1), 500 (1), 75 (1) |
| CommissionPct | NUMERIC | NOT NULL | Commission percent received per sale (fraction). | values: 0.01 (4), 0.015 (3), 0 (3), 0.018 (2), 0.012 (2), 0.02 (1), 0.019 (1), 0.016 (1) |
| SalesYTD | NUMERIC | NOT NULL | Sales total year to date (stored snapshot value). | range 172524.4512 .. 4251368.5497, avg 2.13398e+06 |
| SalesLastYear | NUMERIC | NOT NULL | Sales total of the previous year (stored snapshot value). | values: 0 (4), 2396539.7601 (1), 2278548.9776 (1), 2073505.9999 (1), 2038234.6549 (1), 1997186.2037 (1), 1927059.178 (1), 1849640.9418 (1), 1750406.4785 (1), 1635823.3967 (1), 1620276.8966 (1), 1439156.0291 (1), 1371635.3158 (1), 1307949.7917 (1) |
| rowguid | TEXT | NOT NULL |  | values: '1DD1F689-DF74-4149-8600-59555EEF154B', '1E0A7274-3064-4F58-88EE-4C6586C87169', '224BB25A-62E3-493E-ACAF-4F8F5C72396A', '25F6838D-9DB4-4833-9DDC-7A24283AF1BA', '31FD7FC1-DC84-4F05-B9A0-762519EACACC', '35326DDB-7278-4FEF-B3BA-EA137B69094E', '39012928-BFEC-4242-874D-423162C3F567', '48754992-9EE0-4C0E-8C94-9451604E3E02', '4DD9EEE4-8E81-4F8C-AF97-683394C1F7C0', '52A5179D-3239-4157-AE29-17E868296DC0', '6BAC15B2-8FFB-45A9-B6D5-040E16C2073F', '7A0AE1AB-B283-40F9-91D1-167ABF06D720', '9B968777-75DC-45BD-A8DF-9CDAA72839E1', 'AC94EC04-A2DC-43E3-8654-DD0C546ABC17', 'BE941A4A-FB50-4947-BDA4-BB8972365B08', 'CFDBEF27-B1F7-4A56-A878-0221C73BAE67', 'F509E3D4-76C8-42AA-B353-90B7B8DB08DE' |
| ModifiedDate | TEXT | NOT NULL |  | range 2021-12-27T00:00:00 .. 2024-05-22T00:00:00 |

## Relationships

- Sales__SalesOrderHeader.SalesPersonID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__SalesPerson.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
- Sales__SalesPerson.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesPersonQuotaHistory.BusinessEntityID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__SalesTerritoryHistory.BusinessEntityID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__Store.SalesPersonID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__SalesPerson.BusinessEntityID = Person__Person.BusinessEntityID  [curated; Sales person name (same BusinessEntityID; shortcut instead of going through HumanResources__Employee).]

**Unique indexes:** Sales__SalesPerson__AK_SalesPerson_rowguid (rowguid)

## Business definitions

- **Quota attainment**: Sales person year-to-date sales divided by their sales quota.

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

