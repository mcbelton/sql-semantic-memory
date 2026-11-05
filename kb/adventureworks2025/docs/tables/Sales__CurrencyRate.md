# Sales__CurrencyRate

**Type:** table | **Domain:** Sales | **Rows:** 13,532 | **SQL name:** `Sales__CurrencyRate`

Daily currency exchange rates from USD to other currencies.

**Synonyms:** exchange rates, fx rates

**Primary key:** CurrencyRateID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CurrencyRateID | INTEGER | PK, NOT NULL |  | range 1 .. 13532 |
| CurrencyRateDate | TEXT | NOT NULL |  | range 2022-05-30T00:00:00 .. 2025-05-30T00:00:00 |
| FromCurrencyCode | TEXT | FK -> Sales__Currency.CurrencyCode, NOT NULL | Currency converted from (always USD). | values: 'USD' (13,532) |
| ToCurrencyCode | TEXT | FK -> Sales__Currency.CurrencyCode, NOT NULL | Currency converted to. | values: 'VEB' (1,097), 'USD' (1,097), 'SAR' (1,097), 'MXN' (1,097), 'JPY' (1,097), 'GBP' (1,097), 'EUR' (1,097), 'CNY' (1,097), 'CAD' (1,097), 'BRL' (1,097), 'AUD' (1,097), 'ARS' (1,097), 'FRF' (184), 'DEM' (184) |
| AverageRate | NUMERIC | NOT NULL | Average exchange rate for the day. | range 0.6046 .. 1500, avg 79.2363 |
| EndOfDayRate | NUMERIC | NOT NULL | Final exchange rate for the day. | range 0.6041 .. 1499.95, avg 79.2363 |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-05-30T00:00:00 .. 2025-05-30T00:00:00 |

## Relationships

- Sales__CurrencyRate.FromCurrencyCode = Sales__Currency.CurrencyCode  [declared]
- Sales__CurrencyRate.ToCurrencyCode = Sales__Currency.CurrencyCode  [declared]
- Sales__SalesOrderHeader.CurrencyRateID = Sales__CurrencyRate.CurrencyRateID  [declared]

**Unique indexes:** Sales__CurrencyRate__AK_CurrencyRate_CurrencyRateDate_FromCurrencyCode_ToCurrencyCode (CurrencyRateDate, FromCurrencyCode, ToCurrencyCode)
