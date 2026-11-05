# Person__PersonPhone

**Type:** table | **Domain:** Person | **Rows:** 19,972 | **SQL name:** `Person__PersonPhone`

Phone numbers of people with phone type.

**Primary key:** BusinessEntityID, PhoneNumber, PhoneNumberTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL |  | range 1 .. 20777 |
| PhoneNumber | TEXT | PK, NOT NULL |  | sensitive - values not captured |
| PhoneNumberTypeID | INTEGER | PK, FK -> Person__PhoneNumberType.PhoneNumberTypeID, NOT NULL |  | range 1 .. 3 |
| ModifiedDate | TEXT | NOT NULL |  | range 2015-04-15T16:33:33.060000 .. 2025-06-29T00:00:00 |

## Relationships

- Person__PersonPhone.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Person__PersonPhone.PhoneNumberTypeID = Person__PhoneNumberType.PhoneNumberTypeID  [declared]
