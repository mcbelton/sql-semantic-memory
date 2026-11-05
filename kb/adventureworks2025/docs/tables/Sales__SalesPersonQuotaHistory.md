# Sales__SalesPersonQuotaHistory

**Type:** table | **Domain:** Sales | **Rows:** 163 | **SQL name:** `Sales__SalesPersonQuotaHistory`

Sales quota history per sales person and quota date (quarterly quotas).

**Primary key:** BusinessEntityID, QuotaDate

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Sales__SalesPerson.BusinessEntityID, NOT NULL |  | range 274 .. 290 |
| QuotaDate | TEXT | PK, NOT NULL | Date the quota applies from. | range 2022-05-30T00:00:00 .. 2025-02-28T00:00:00 |
| SalesQuota | NUMERIC | NOT NULL | Sales quota amount for the period. | range 1000 .. 1898000, avg 587202 |
| rowguid | TEXT | NOT NULL |  | e.g. '00F2F9F8-5158-4436-B134-7E0C462289E5', '0103899F-618C-4478-90BB-815B20856F35', '0323D0BC-C5CC-4D67-8935-DD05074FBA43' (163 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-15T00:00:00 .. 2025-01-14T00:00:00 |

## Relationships

- Sales__SalesPersonQuotaHistory.BusinessEntityID = Sales__SalesPerson.BusinessEntityID  [declared]

**Unique indexes:** Sales__SalesPersonQuotaHistory__AK_SalesPersonQuotaHistory_rowguid (rowguid)
