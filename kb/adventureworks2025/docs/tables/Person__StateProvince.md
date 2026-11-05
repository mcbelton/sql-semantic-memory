# Person__StateProvince

**Type:** table | **Domain:** Person | **Rows:** 181 | **SQL name:** `Person__StateProvince`

States and provinces with their country and sales territory.

**Synonyms:** states, provinces, regions

**Primary key:** StateProvinceID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| StateProvinceID | INTEGER | PK, NOT NULL |  | range 1 .. 181 |
| StateProvinceCode | TEXT | NOT NULL | ISO standard state or province code. | e.g. '01 ', '02 ', '03 ' (181 distinct) |
| CountryRegionCode | TEXT | FK -> Person__CountryRegion.CountryRegionCode, NOT NULL |  | values: 'FR' (96), 'US' (53), 'CA' (13), 'DE' (7), 'AU' (5), 'VI' (1), 'PW' (1), 'MP' (1), 'MH' (1), 'GB' (1), 'FM' (1), 'AS' (1) |
| IsOnlyStateProvinceFlag | TEXT | NOT NULL | Whether a real state/province code exists. | codes: 0=StateProvinceCode exists, 1=Unavailable - CountryRegionCode used instead; values: '0' (173), '1' (8) |
| Name | TEXT | NOT NULL |  | e.g. 'Ain', 'Aisne', 'Alabama' (181 distinct) |
| TerritoryID | INTEGER | FK -> Sales__SalesTerritory.TerritoryID, NOT NULL | Sales territory the state/province belongs to. | range 1 .. 10 |
| rowguid | TEXT | NOT NULL |  | e.g. '00723E00-C976-401D-A92B-E582DF3D6E01', '01CEC802-20CE-4F96-B475-2AD263CEA9D0', '0374FD8E-3A19-4A9B-BB9E-DB5871503AFE' (181 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2025-02-07T10:17:21.587000 |

## Relationships

- Person__Address.StateProvinceID = Person__StateProvince.StateProvinceID  [declared]
- Person__StateProvince.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]
- Person__StateProvince.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]
- Sales__SalesTaxRate.StateProvinceID = Person__StateProvince.StateProvinceID  [declared]

**Unique indexes:** Person__StateProvince__AK_StateProvince_Name (Name); Person__StateProvince__AK_StateProvince_StateProvinceCode_CountryRegionCode (StateProvinceCode, CountryRegionCode); Person__StateProvince__AK_StateProvince_rowguid (rowguid)

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

