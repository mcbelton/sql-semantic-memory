# Sales__SalesTaxRate

**Type:** table | **Domain:** Sales | **Rows:** 29 | **SQL name:** `Sales__SalesTaxRate`

Tax rates per state/province.

**Primary key:** SalesTaxRateID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SalesTaxRateID | INTEGER | PK, NOT NULL |  | range 1 .. 31 |
| StateProvinceID | INTEGER | FK -> Person__StateProvince.StateProvinceID, NOT NULL |  | range 1 .. 84 |
| TaxType | INTEGER | NOT NULL | Which transactions the tax applies to. | codes: 1=Retail transactions, 2=Wholesale transactions, 3=All sales (retail and wholesale); values: 3 (13), 1 (13), 2 (3) |
| TaxRate | NUMERIC | NOT NULL | Tax rate in percent (7.25 = 7.25%). | values: 7 (13), 14.25 (2), 7.25 (2), 19.6 (1), 17.5 (1), 16 (1), 14 (1), 10 (1), 8.8 (1), 8.75 (1), 8 (1), 7.75 (1), 7.5 (1), 6.75 (1), 5 (1) |
| Name | TEXT | NOT NULL |  | values: 'Canadian GST' (12), 'Washington State Sales Tax' (1), 'Utah State Sales Tax' (1), 'United Kingdom Output Tax' (1), 'Texas State Sales Tax' (1), 'Tennessese State Sales Tax' (1), 'Taxable Supply' (1), 'Minnesota State Sales Tax' (1), 'Michigan State Sales Tax' (1), 'Massachusetts State Sales Tax' (1), 'Germany Output Tax' (1), 'France Output Tax' (1), 'Florida State Sales Tax' (1), 'Canadian GST + Quebec Provincial Tax' (1), 'Canadian GST + Ontario Provincial Tax' (1), 'Canadian GST + Alberta Provincial Tax' (1), 'California State Sales Tax' (1), 'Arizona State Sales Tax' (1) |
| rowguid | TEXT | NOT NULL |  | e.g. '05C4FFDB-4F84-4CDF-ABE5-FDF3216EA74E', '06DF529D-EB11-446F-9570-9EE97B8EA1BF', '1753D75F-8357-4497-BC92-543F17BBF514' (29 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Sales__SalesTaxRate.StateProvinceID = Person__StateProvince.StateProvinceID  [declared]

**Unique indexes:** Sales__SalesTaxRate__AK_SalesTaxRate_StateProvinceID_TaxType (StateProvinceID, TaxType); Sales__SalesTaxRate__AK_SalesTaxRate_rowguid (rowguid)
