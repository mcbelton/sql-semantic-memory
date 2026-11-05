# Person__BusinessEntityAddress

**Type:** table | **Domain:** Person | **Rows:** 19,614 | **SQL name:** `Person__BusinessEntityAddress`

Cross-reference mapping people, stores and vendors to their addresses (with address type).

**Primary key:** BusinessEntityID, AddressID, AddressTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__BusinessEntity.BusinessEntityID, NOT NULL |  | range 1 .. 20777 |
| AddressID | INTEGER | PK, FK -> Person__Address.AddressID, NOT NULL |  | range 1 .. 32521 |
| AddressTypeID | INTEGER | PK, FK -> Person__AddressType.AddressTypeID, NOT NULL |  | range 2 .. 5 |
| rowguid | TEXT | NOT NULL |  | e.g. '00013363-E32F-4615-9439-AFF156D480AE', '0001CCDA-AD2B-4BBE-8047-CAC51EFDBB53', '0006A62C-C87F-448E-AE91-F01A2F34466C'; 19,614 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-24T00:00:00 .. 2025-09-11T11:15:06.967000 |

## Relationships

- Person__BusinessEntityAddress.AddressID = Person__Address.AddressID  [declared]
- Person__BusinessEntityAddress.AddressTypeID = Person__AddressType.AddressTypeID  [declared]
- Person__BusinessEntityAddress.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]

**Unique indexes:** Person__BusinessEntityAddress__AK_BusinessEntityAddress_rowguid (rowguid)
