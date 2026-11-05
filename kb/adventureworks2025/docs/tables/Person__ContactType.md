# Person__ContactType

**Type:** table | **Domain:** Person | **Rows:** 20 | **SQL name:** `Person__ContactType`

Roles of business contacts (Owner, Purchasing Agent, Marketing Manager, ...).

**Primary key:** ContactTypeID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ContactTypeID | INTEGER | PK, NOT NULL |  | range 1 .. 20 |
| Name | TEXT | NOT NULL |  | values: 'Accounting Manager', 'Assistant Sales Agent', 'Assistant Sales Representative', 'Coordinator Foreign Markets', 'Export Administrator', 'International Marketing Manager', 'Marketing Assistant', 'Marketing Manager', 'Marketing Representative', 'Order Administrator', 'Owner', 'Owner/Marketing Assistant', 'Product Manager', 'Purchasing Agent', 'Purchasing Manager', 'Regional Account Representative', 'Sales Agent', 'Sales Associate', 'Sales Manager', 'Sales Representative' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Person__BusinessEntityContact.ContactTypeID = Person__ContactType.ContactTypeID  [declared]

**Unique indexes:** Person__ContactType__AK_ContactType_Name (Name)
