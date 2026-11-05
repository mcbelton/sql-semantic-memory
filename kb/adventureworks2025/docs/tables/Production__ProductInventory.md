# Production__ProductInventory

**Type:** table | **Domain:** Production | **Rows:** 1,069 | **SQL name:** `Production__ProductInventory`

Current inventory quantity of each product per location (shelf/bin).

**Synonyms:** inventory, stock, on hand

**Primary key:** ProductID, LocationID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 1 .. 999 |
| LocationID | INTEGER | PK, FK -> Production__Location.LocationID, NOT NULL | Inventory location. Join Production__Location. | range 1 .. 60 |
| Shelf | TEXT | NOT NULL | Storage compartment within the location. | values: 'N/A' (290), 'G' (96), 'E' (85), 'A' (81), 'R' (61), 'F' (59), 'C' (55), 'D' (50), 'U' (38), 'H' (37), 'B' (36), 'L' (33), 'K' (29), 'T' (28), 'J' (27), 'S' (17), 'W' (14), 'M' (14), 'N' (10), 'V' (7), ... (21 distinct) |
| Bin | INTEGER | NOT NULL | Storage container on a shelf. | range 0 .. 61, avg 8.89991 |
| Quantity | INTEGER | NOT NULL | Quantity of the product in the location. | range 0 .. 924, avg 314.288 |
| rowguid | TEXT | NOT NULL |  | e.g. '47A24246-6C43-48EB-968F-025738A8A410', 'D4544D7D-CAF5-46B3-AB22-5718DCC26B5E', 'BFF7DC60-96A8-43CA-81A7-D6D2ED3000A8'; 1,069 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-03-31T00:00:00 .. 2025-08-11T00:00:00 |

## Relationships

- Production__ProductInventory.LocationID = Production__Location.LocationID  [declared]
- Production__ProductInventory.ProductID = Production__Product.ProductID  [declared]

## Business definitions

- **Inventory on hand**: Units currently in stock, summed over all locations.

## Example queries

**Products at or below their reorder point (inventory across all locations)**

```sql
SELECT p.ProductNumber, p.Name, p.ReorderPoint, p.SafetyStockLevel, COALESCE(SUM(i.Quantity), 0) AS on_hand
FROM Production__Product p
LEFT JOIN Production__ProductInventory i ON i.ProductID = p.ProductID
WHERE p.SellEndDate IS NULL AND p.DiscontinuedDate IS NULL
GROUP BY p.ProductID, p.ProductNumber, p.Name, p.ReorderPoint, p.SafetyStockLevel
HAVING COALESCE(SUM(i.Quantity), 0) <= p.ReorderPoint
ORDER BY on_hand;
```

