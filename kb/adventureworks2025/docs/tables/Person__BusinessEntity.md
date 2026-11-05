# Person__BusinessEntity

**Type:** table | **Domain:** Person | **Rows:** 20,777 | **SQL name:** `Person__BusinessEntity`

Source of the BusinessEntityID shared by people, stores and vendors (the common key for addresses and contacts).

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, NOT NULL |  | range 1 .. 20777 |
| rowguid | TEXT | NOT NULL |  | e.g. '00021813-91EF-4A97-9682-0D2AC8C9EA97', '000392B5-933E-4BFF-945B-FF50AABBB7C0', '00046B88-5FAB-4922-B671-C080FD04CDC9'; 20,777 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-12-13T13:20:24.150000 .. 2017-12-13T13:47:22.467000 |

## Relationships

- Person__BusinessEntityAddress.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Person__BusinessEntityContact.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Person__Person.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Purchasing__Vendor.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]
- Sales__Store.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]

**Unique indexes:** Person__BusinessEntity__AK_BusinessEntity_rowguid (rowguid)
