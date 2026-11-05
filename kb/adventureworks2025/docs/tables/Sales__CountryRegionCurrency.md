# Sales__CountryRegionCurrency

**Type:** table | **Domain:** Sales | **Rows:** 109 | **SQL name:** `Sales__CountryRegionCurrency`

Cross-reference mapping countries/regions to their ISO currency codes.

**Primary key:** CountryRegionCode, CurrencyCode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CountryRegionCode | TEXT | PK, FK -> Person__CountryRegion.CountryRegionCode, NOT NULL |  | values: 'AT' (2), 'BE' (2), 'DE' (2), 'ES' (2), 'FI' (2), 'FR' (2), 'GR' (2), 'IE' (2), 'IT' (2), 'NL' (2), 'PL' (2), 'PT' (2), 'RU' (2), 'AE' (1), 'AR' (1), 'AU' (1), 'BB' (1), 'BD' (1), 'BG' (1), 'BH' (1), ... (96 distinct) |
| CurrencyCode | TEXT | PK, FK -> Sales__Currency.CurrencyCode, NOT NULL |  | values: 'EUR' (12), 'USD' (2), 'AED' (1), 'ARS' (1), 'ATS' (1), 'AUD' (1), 'BBD' (1), 'BDT' (1), 'BEF' (1), 'BGN' (1), 'BHD' (1), 'BND' (1), 'BOB' (1), 'BRL' (1), 'BSD' (1), 'BTN' (1), 'CAD' (1), 'CHF' (1), 'CLP' (1), 'CNY' (1), ... (97 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2025-02-07T10:17:21.510000 |

## Relationships

- Sales__CountryRegionCurrency.CountryRegionCode = Person__CountryRegion.CountryRegionCode  [declared]
- Sales__CountryRegionCurrency.CurrencyCode = Sales__Currency.CurrencyCode  [declared]
