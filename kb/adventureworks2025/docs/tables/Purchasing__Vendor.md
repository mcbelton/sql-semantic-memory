# Purchasing__Vendor

**Type:** table | **Domain:** Purchasing | **Rows:** 104 | **SQL name:** `Purchasing__Vendor`

Companies from which Adventure Works purchases parts and other goods.

**Synonyms:** suppliers, vendors, manufacturers

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__BusinessEntity.BusinessEntityID, NOT NULL | Primary key; referenced by PurchaseOrderHeader.VendorID and ProductVendor. | range 1492 .. 1698 |
| AccountNumber | TEXT | NOT NULL | Vendor account (identification) number. | e.g. 'ADATUM0001', 'ADVANCED0001', 'ALLENSON0001' (104 distinct) |
| Name | TEXT | NOT NULL | Company name. | e.g. 'Wood Fitness', 'Wide World Importers', 'WestAmerica Bicycle Co.' (104 distinct) |
| CreditRating | INTEGER | NOT NULL | Vendor credit rating. | codes: 1=Superior, 2=Excellent, 3=Above average, 4=Average, 5=Below average; values: 1 (84), 2 (9), 3 (7), 5 (2), 4 (2) |
| PreferredVendorStatus | TEXT | NOT NULL | Preferred vendor flag. | codes: 0=Do not use if another vendor is available, 1=Preferred over other vendors supplying the same product; values: '1' (93), '0' (11) |
| ActiveFlag | TEXT | NOT NULL | Whether the vendor is still used. | codes: 0=Vendor no longer used, 1=Vendor actively used; values: '1' (100), '0' (4) |
| PurchasingWebServiceURL | TEXT |  | Vendor web service URL. | values: 'www.wideworldimporters.com/', 'www.treyresearch.net/', 'www.proseware.com/', 'www.northwindtraders.com/', 'www.litwareinc.com/', 'www.adatum.com/'; 94.23% null |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-04-24T00:00:00 .. 2023-02-17T00:00:00 |

## Relationships

- Purchasing__ProductVendor.BusinessEntityID = Purchasing__Vendor.BusinessEntityID  [declared]
- Purchasing__PurchaseOrderHeader.VendorID = Purchasing__Vendor.BusinessEntityID  [declared]
- Purchasing__Vendor.BusinessEntityID = Person__BusinessEntity.BusinessEntityID  [declared]

**Unique indexes:** Purchasing__Vendor__AK_Vendor_AccountNumber (AccountNumber)

## Example queries

**Top 10 vendors by purchase spend**

```sql
SELECT v.Name AS vendor, COUNT(*) AS purchase_orders, ROUND(SUM(poh.SubTotal), 2) AS spend
FROM Purchasing__PurchaseOrderHeader poh
JOIN Purchasing__Vendor v ON v.BusinessEntityID = poh.VendorID
WHERE poh.Status <> 3
GROUP BY v.BusinessEntityID, v.Name
ORDER BY spend DESC
LIMIT 10;
```

