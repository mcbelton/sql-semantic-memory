# Sales__SalesTerritoryHistory

**Type:** table | **Domain:** Sales | **Rows:** 17 | **SQL name:** `Sales__SalesTerritoryHistory`

History of sales person assignments to territories (StartDate/EndDate; EndDate NULL = current).

**Primary key:** BusinessEntityID, StartDate, TerritoryID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Sales__SalesPerson.BusinessEntityID, NOT NULL |  | range 275 .. 290 |
| TerritoryID | INTEGER | PK, FK -> Sales__SalesTerritory.TerritoryID, NOT NULL |  | range 1 .. 10 |
| StartDate | TEXT | PK, NOT NULL |  | range 2022-05-30T00:00:00 .. 2024-05-29T00:00:00 |
| EndDate | TEXT |  | Date the assignment ended; NULL = current assignment. | range 2023-05-29T00:00:00 .. 2023-11-29T00:00:00; 76.47% null |
| rowguid | TEXT | NOT NULL |  | values: '009F7660-44A6-4ADF-BD4B-A5D1B79993F5', '132E4721-32DD-4A73-B556-1837F3A2B9AE', '2C9F5240-D8BF-4F85-897D-6083146DBC4B', '2F44304C-EE87-4C72-813E-CA75C5F61F4C', '3E1360CB-32E0-4286-8D98-8539F1AB2550', '3E9F893D-5142-46C9-A76A-867D1E3D6F90', '57D1CDCF-62CE-499F-8BE8-1BB71C4BB7EF', '64BCB1B3-A793-40BA-9859-D90F78C3F167', '8563CE6A-00FF-47D7-BA4D-3C3E1CDEF531', '8895E74D-6D38-4140-BBEA-A8136A2F480E', '92375465-38C6-4C86-ABA1-9838A2969475', '987613ED-33D6-42A6-B992-0B33E9234934', '9D8754B2-C320-40DB-A77F-FF5A1BC0F46B', 'B7C8F9F5-5FB8-47B3-BE73-1B9A14BDF8B9', 'D664D989-2BEB-4F2C-A4AA-691018965283', 'ED12F921-8023-48EF-84BD-94D942F4C009', 'FD3F5566-10E2-4960-BE12-0365E5665881' |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-05-23T00:00:00 .. 2024-05-22T00:00:00 |

## Relationships

- Sales__SalesTerritoryHistory.BusinessEntityID = Sales__SalesPerson.BusinessEntityID  [declared]
- Sales__SalesTerritoryHistory.TerritoryID = Sales__SalesTerritory.TerritoryID  [declared]

**Unique indexes:** Sales__SalesTerritoryHistory__AK_SalesTerritoryHistory_rowguid (rowguid)
