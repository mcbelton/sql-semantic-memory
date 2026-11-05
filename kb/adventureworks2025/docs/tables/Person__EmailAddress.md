# Person__EmailAddress

**Type:** table | **Domain:** Person | **Rows:** 19,972 | **SQL name:** `Person__EmailAddress`

E-mail addresses of people.

**Primary key:** BusinessEntityID, EmailAddressID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL |  | range 1 .. 20777 |
| EmailAddressID | INTEGER | PK, NOT NULL |  | range 1 .. 19972 |
| EmailAddress | TEXT |  |  | sensitive - values not captured |
| rowguid | TEXT | NOT NULL |  | e.g. '8A1901E4-671B-431A-871C-EADB2942E9EE', 'B5FF9EFD-72A2-4F87-830B-F338FDD4D162', 'C8A51084-1C03-4C58-A8B3-55854AE7C499'; 19,972 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2015-04-15T16:33:33.060000 .. 2025-06-29T00:00:00 |

## Relationships

- Person__EmailAddress.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
