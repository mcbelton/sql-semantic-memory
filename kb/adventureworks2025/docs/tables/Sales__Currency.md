# Sales__Currency

**Type:** table | **Domain:** Sales | **Rows:** 105 | **SQL name:** `Sales__Currency`

Lookup of ISO currency codes and names.

**Synonyms:** currencies

**Primary key:** CurrencyCode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CurrencyCode | TEXT | PK, NOT NULL |  | e.g. 'AED', 'AFA', 'ALL' (105 distinct) |
| Name | TEXT | NOT NULL |  | e.g. 'Afghani', 'Algerian Dinar', 'Argentine Peso' (105 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Sales__CountryRegionCurrency.CurrencyCode = Sales__Currency.CurrencyCode  [declared]
- Sales__CurrencyRate.FromCurrencyCode = Sales__Currency.CurrencyCode  [declared]
- Sales__CurrencyRate.ToCurrencyCode = Sales__Currency.CurrencyCode  [declared]

**Unique indexes:** Sales__Currency__AK_Currency_Name (Name)
