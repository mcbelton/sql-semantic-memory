# Person__Address

**Type:** table | **Domain:** Person | **Rows:** 19,614 | **SQL name:** `Person__Address`

Street addresses of customers, employees, stores and vendors.

**Synonyms:** addresses, locations, cities

**Primary key:** AddressID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| AddressID | INTEGER | PK, NOT NULL |  | range 1 .. 32521 |
| AddressLine1 | TEXT | NOT NULL |  | sensitive - values not captured |
| AddressLine2 | TEXT |  |  | sensitive - values not captured; 98.15% null |
| City | TEXT | NOT NULL | City name. | e.g. 'Ottawa', 'Burnaby', 'Dunkerque'; 575 distinct |
| StateProvinceID | INTEGER | FK -> Person__StateProvince.StateProvinceID, NOT NULL | State/province. Join Person__StateProvince (-> Person__CountryRegion for the country). | range 1 .. 181 |
| PostalCode | TEXT | NOT NULL | Postal (ZIP) code. | e.g. 'K4B 1S2', 'V5A 4X1', '59140'; 661 distinct |
| SpatialLocation | BLOB |  | Latitude/longitude (binary geography, not queryable here). |  |
| rowguid | TEXT | NOT NULL |  | e.g. '00093F9C-0487-4723-B376-D90FF565AD6F', '000A2255-2D8E-4D99-B82F-7013B256EE31', '000A5A3E-E89A-4B5D-A3F8-3D8595D8A7F0'; 19,614 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-06-22T00:00:00 .. 2025-06-29T00:00:00 |

## Relationships

- Person__Address.StateProvinceID = Person__StateProvince.StateProvinceID  [declared]
- Person__BusinessEntityAddress.AddressID = Person__Address.AddressID  [declared]
- Sales__SalesOrderHeader.BillToAddressID = Person__Address.AddressID  [declared]
- Sales__SalesOrderHeader.ShipToAddressID = Person__Address.AddressID  [declared]

**Unique indexes:** Person__Address__AK_Address_rowguid (rowguid); Person__Address__IX_Address_AddressLine1_AddressLine2_City_StateProvinceID_PostalCode (AddressLine1, AddressLine2, City, StateProvinceID, PostalCode)

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

