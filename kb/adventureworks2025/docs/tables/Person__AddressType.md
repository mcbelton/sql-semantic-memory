# Person__AddressType

**Type:** table | **Domain:** Person | **Rows:** 6 | **SQL name:** `Person__AddressType`

Types of addresses (Billing, Home, Main Office, Primary, Shipping, Archive).

**Primary key:** AddressTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| AddressTypeID | INTEGER | PK, NOT NULL |  | range 1 .. 6 |
| Name | TEXT | NOT NULL |  | values: 'Archive', 'Billing', 'Home', 'Main Office', 'Primary', 'Shipping' |
| rowguid | TEXT | NOT NULL |  | values: '24CB3088-4345-47C4-86C5-17B535133D1E', '41BC2FF6-F0FC-475F-8EB9-CEC0805AA0F2', '8EEEC28C-07A2-4FB9-AD0A-42D4A0BBC575', 'A67F238A-5BA2-444B-966C-0467ED9C427F', 'B29DA3F8-19A3-47DA-9DAA-15C84F4A83A5', 'B84F78B1-4EFE-4A0E-8CB7-70E9F112F886' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Person__BusinessEntityAddress.AddressTypeID = Person__AddressType.AddressTypeID  [declared]

**Unique indexes:** Person__AddressType__AK_AddressType_Name (Name); Person__AddressType__AK_AddressType_rowguid (rowguid)
