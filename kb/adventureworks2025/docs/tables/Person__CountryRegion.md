# Person__CountryRegion

**Type:** table | **Domain:** Person | **Rows:** 238 | **SQL name:** `Person__CountryRegion`

ISO country/region codes and names.

**Synonyms:** countries, nations

**Primary key:** CountryRegionCode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CountryRegionCode | TEXT | PK, NOT NULL |  | e.g. 'AD', 'AE', 'AF' (238 distinct) |
| Name | TEXT | NOT NULL |  | e.g. 'Afghanistan', 'Albania', 'Algeria' (238 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Person__StateProvince.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]
- Sales__CountryRegionCurrency.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]
- Sales__SalesTerritory.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]

**Unique indexes:** Person__CountryRegion__AK_CountryRegion_Name (Name)

## Example queries

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

