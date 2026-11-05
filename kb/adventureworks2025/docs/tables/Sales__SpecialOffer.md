# Sales__SpecialOffer

**Type:** table | **Domain:** Sales | **Rows:** 16 | **SQL name:** `Sales__SpecialOffer`

Promotions and discounts (volume discounts, seasonal sales, clearance, etc.).

**Synonyms:** promotions, discounts, offers, deals

**Primary key:** SpecialOfferID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| SpecialOfferID | INTEGER | PK, NOT NULL |  | range 1 .. 16 |
| Description | TEXT | NOT NULL | Offer name. | values: 'Volume Discount over 60', 'Volume Discount 41 to 60', 'Volume Discount 25 to 40', 'Volume Discount 15 to 24', 'Volume Discount 11 to 14', 'Touring-3000 Promotion', 'Touring-1000 Promotion', 'Sport Helmet Discount-2003', 'Sport Helmet Discount-2002', 'Road-650 Overstock', 'No Discount', 'Mountain-500 Silver Clearance Sale', 'Mountain-100 Clearance Sale', 'Mountain Tire Sale', 'LL Road Frame Sale', 'Half-Price Pedal Sale' |
| DiscountPct | NUMERIC | NOT NULL | Discount percentage as a fraction (0.15 = 15%). | values: 0.15 (3), 0.5 (2), 0.35 (2), 0.2 (2), 0.1 (2), 0.4 (1), 0.3 (1), 0.05 (1), 0.02 (1), 0 (1) |
| Type | TEXT | NOT NULL | Discount type category. | values: 'Volume Discount' (5), 'Seasonal Discount' (3), 'Excess Inventory' (3), 'New Product' (2), 'Discontinued Product' (2), 'No Discount' (1) |
| Category | TEXT | NOT NULL | Who the discount applies to: Reseller, Customer or No Discount. | values: 'Reseller' (13), 'Customer' (2), 'No Discount' (1) |
| StartDate | TEXT | NOT NULL |  | range 2022-04-30T00:00:00 .. 2025-03-30T00:00:00 |
| EndDate | TEXT | NOT NULL |  | range 2023-05-29T00:00:00 .. 2025-11-29T00:00:00 |
| MinQty | INTEGER | NOT NULL | Minimum quantity for the discount. | values: 0 (11), 61 (1), 41 (1), 25 (1), 15 (1), 11 (1) |
| MaxQty | INTEGER |  | Maximum quantity for the discount. | range 14 .. 60, avg 34.5; 75.0% null |
| rowguid | TEXT | NOT NULL |  | values: '0290C4F5-191F-4337-AB6B-0A2DDE03CBF9', '03E3594D-6EBB-46A6-B8EE-A9289C0C2E47', '0CF8472B-F9E6-4945-9E09-549D7DDE2198', '1AF84A9E-A98C-4BD9-B48F-DC2B8B6B010B', '20C5D2CC-A38F-48F8-AC9A-8F15943E52AE', '220444AD-2EF3-4E4C-87E9-3AA6EE39A877', '4BDBCC01-8CF7-40A9-B643-40EC5B717491', '504B5E85-8F3F-4EBC-9E1D-C1BC5DEA9AA8', '5061CCE4-E021-45A8-9A75-DFB36CBBCE85', '677E1D9D-944F-4E81-90E8-47EB0A82D48C', '7DF15BF5-6C05-47E7-80A4-22BD1CE59A72', '8157F569-4E8D-46B6-9347-5D0F726A9439', 'C0AF1C89-9722-4235-9248-3FBA4D9E5841', 'D7542EE7-15DB-4541-985C-5CC27AEF26D6', 'E72DAB1D-F44D-448B-9FE2-F259A2F0210D', 'EB7CB484-BCCF-4D2D-BF73-521B20014174' |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-03-31T00:00:00 .. 2025-02-28T00:00:00 |

## Relationships

- Sales__SpecialOfferProduct.SpecialOfferID = Sales__SpecialOffer.SpecialOfferID  [declared]
- Sales__SalesOrderDetail.SpecialOfferID = Sales__SpecialOffer.SpecialOfferID  [inferred]

**Unique indexes:** Sales__SpecialOffer__AK_SpecialOffer_rowguid (rowguid)

## Example queries

**Discount amount and revenue by special offer**

```sql
SELECT so.Description AS offer, so.Type, so.Category, COUNT(*) AS order_lines,
       ROUND(SUM(d.OrderQty * d.UnitPrice * d.UnitPriceDiscount), 2) AS discount_amount,
       ROUND(SUM(d.LineTotal), 2) AS revenue
FROM Sales__SalesOrderDetail d
JOIN Sales__SpecialOffer so ON so.SpecialOfferID = d.SpecialOfferID
GROUP BY so.SpecialOfferID, so.Description, so.Type, so.Category
ORDER BY discount_amount DESC;
```

