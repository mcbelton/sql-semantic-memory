# Person__PhoneNumberType

**Type:** table | **Domain:** Person | **Rows:** 3 | **SQL name:** `Person__PhoneNumberType`

Phone number types (Cell, Home, Work).

**Primary key:** PhoneNumberTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| PhoneNumberTypeID | INTEGER | PK, NOT NULL |  | range 1 .. 3 |
| Name | TEXT | NOT NULL |  | values: 'Work', 'Home', 'Cell' |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-12-13T13:19:22.273000 .. 2017-12-13T13:19:22.273000 |

## Relationships

- Person__PersonPhone.PhoneNumberTypeID = Person__PhoneNumberType.PhoneNumberTypeID  [declared]
