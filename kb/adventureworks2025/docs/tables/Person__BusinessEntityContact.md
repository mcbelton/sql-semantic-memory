# Person__BusinessEntityContact

**Type:** table | **Domain:** Person | **Rows:** 909 | **SQL name:** `Person__BusinessEntityContact`

Cross-reference mapping stores and vendors to their contact people (with contact type).

**Primary key:** BusinessEntityID, PersonID, ContactTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__BusinessEntity.BusinessEntityID, NOT NULL |  | range 292 .. 2051 |
| PersonID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL |  | range 291 .. 2090 |
| ContactTypeID | INTEGER | PK, FK -> Person__ContactType.ContactTypeID, NOT NULL |  | range 2 .. 19 |
| rowguid | TEXT | NOT NULL |  | e.g. '0022434C-E325-47B0-92A0-7302FFA5046F', '00A811E1-D1A5-47B0-8D94-1C6FBAC4C743', '01422957-23AE-4079-AFBA-07000F64B4A1'; 909 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-12-13T13:21:02.243000 .. 2023-02-17T00:00:00 |

## Relationships

- Person__BusinessEntityContact.PersonID = Person__Person.BusinessEntityID  [declared]
- Person__BusinessEntityContact.ContactTypeID = Person__ContactType.ContactTypeID  [declared]
- Person__BusinessEntityContact.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]

**Unique indexes:** Person__BusinessEntityContact__AK_BusinessEntityContact_rowguid (rowguid)
