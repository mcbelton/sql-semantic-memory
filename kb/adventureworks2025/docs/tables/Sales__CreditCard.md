# Sales__CreditCard

**Type:** table | **Domain:** Sales | **Rows:** 19,118 | **SQL name:** `Sales__CreditCard`

Customer credit card information.

**Primary key:** CreditCardID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CreditCardID | INTEGER | PK, NOT NULL |  | range 1 .. 19237 |
| CardType | TEXT | NOT NULL | Credit card brand name. | values: 'SuperiorCard' (4,839), 'Distinguish' (4,832), 'ColonialVoice' (4,782), 'Vista' (4,665) |
| CardNumber | TEXT | NOT NULL |  | sensitive - values not captured |
| ExpMonth | INTEGER | NOT NULL | Expiration month. | values: 11 (1,623), 8 (1,619), 9 (1,615), 1 (1,613), 7 (1,611), 12 (1,607), 3 (1,585), 10 (1,584), 5 (1,584), 6 (1,579), 2 (1,553), 4 (1,545) |
| ExpYear | INTEGER | NOT NULL | Expiration year. | values: 2007 (4,832), 2006 (4,807), 2005 (4,743), 2008 (4,736) |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-06-22T00:00:00 .. 2025-06-29T00:00:00 |

## Relationships

- Sales__PersonCreditCard.CreditCardID = Sales__CreditCard.CreditCardID  [declared]
- Sales__SalesOrderHeader.CreditCardID = Sales__CreditCard.CreditCardID  [declared]

**Unique indexes:** Sales__CreditCard__AK_CreditCard_CardNumber (CardNumber)
