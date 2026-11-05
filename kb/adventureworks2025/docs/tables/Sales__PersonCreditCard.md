# Sales__PersonCreditCard

**Type:** table | **Domain:** Sales | **Rows:** 19,118 | **SQL name:** `Sales__PersonCreditCard`

Cross-reference mapping people to their credit cards.

**Primary key:** BusinessEntityID, CreditCardID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL |  | range 293 .. 20777 |
| CreditCardID | INTEGER | PK, FK -> Sales__CreditCard.CreditCardID, NOT NULL |  | range 1 .. 19237 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-05-30T00:00:00 .. 2025-06-29T00:00:00 |

## Relationships

- Sales__PersonCreditCard.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- Sales__PersonCreditCard.CreditCardID = Sales__CreditCard.CreditCardID  [declared]
