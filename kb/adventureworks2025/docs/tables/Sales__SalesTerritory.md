# Sales__SalesTerritory

**Type:** table | **Domain:** Sales | **Rows:** 10 | **SQL name:** `Sales__SalesTerritory`

Sales territories: 5 US regions (Northwest, Northeast, Central, Southwest, Southeast) plus Canada, France, Germany, Australia and United Kingdom, grouped into North America, Europe and Pacific.

**Synonyms:** territories, regions, sales regions, markets

**Primary key:** TerritoryID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| TerritoryID | INTEGER | PK, NOT NULL |  | range 1 .. 10 |
| Name | TEXT | NOT NULL | Territory name. | values: 'Australia', 'Canada', 'Central', 'France', 'Germany', 'Northeast', 'Northwest', 'Southeast', 'Southwest', 'United Kingdom' |
| CountryRegionCode | TEXT | FK -> Person__CountryRegion.CountryRegionCode, NOT NULL | ISO country code. Join Person__CountryRegion. | values: 'US' (5), 'GB' (1), 'FR' (1), 'DE' (1), 'CA' (1), 'AU' (1) |
| Group | TEXT | NOT NULL | Geographic group of the territory (column name is a reserved word: quote it as "Group"). | values: 'North America' (6), 'Europe' (3), 'Pacific' (1) |
| SalesYTD | NUMERIC | NOT NULL | Sales in the territory year to date (stored snapshot value). | range 2402176.8476 .. 10510853.8739, avg 5.27512e+06 |
| SalesLastYear | NUMERIC | NOT NULL | Sales in the territory the previous year (stored snapshot value). | range 1307949.7917 .. 5693988.86, avg 3.27154e+06 |
| CostYTD | NUMERIC | NOT NULL | Business costs in the territory year to date (all 0 here). | values: 0 (10) |
| CostLastYear | NUMERIC | NOT NULL | Business costs in the territory the previous year (all 0 here). | values: 0 (10) |
| rowguid | TEXT | NOT NULL |  | values: '00FB7309-96CC-49E2-8363-0A1BA72486F2', '05FC7E1F-2DEA-414E-9ECD-09D150516FB5', '06B4AF8A-1639-476E-9266-110461D66B00', '43689A10-E30B-497F-B0DE-11DE20267FF7', '602E612E-DFE9-41D9-B894-27E489747885', '6D2450DB-8159-414F-A917-E73EE91C38A9', '6DC4165A-5E4C-42D2-809D-4344E0AC75E7', 'BF806804-9B4C-4B07-9D19-706F2E689552', 'DC3E9EA0-7950-4431-9428-99DBCBC33865', 'DF6E7FD8-1A8D-468C-B103-ED8ADDB452C1' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Person__StateProvince.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__Customer.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesOrderHeader.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesPerson.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesTerritory.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]
- Sales__SalesTerritoryHistory.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]

**Unique indexes:** Sales__SalesTerritory__AK_SalesTerritory_Name (Name); Sales__SalesTerritory__AK_SalesTerritory_rowguid (rowguid)

## Business definitions

- **Region / territory group**: Sales__SalesTerritory."Group" groups territories into North America, Europe and Pacific; Name is the territory (5 US regions or a country).

## Example queries

**Revenue by sales territory in 2024**

```sql
SELECT st.Name AS territory, st."Group" AS region, ROUND(SUM(soh.SubTotal), 2) AS revenue
FROM Sales__SalesOrderHeader soh
JOIN Sales__SalesTerritory st ON st.TerritoryID = soh.TerritoryID
WHERE soh.OrderDate >= '2024-01-01' AND soh.OrderDate < '2025-01-01'
GROUP BY st.Name, st."Group"
ORDER BY revenue DESC;
```

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

