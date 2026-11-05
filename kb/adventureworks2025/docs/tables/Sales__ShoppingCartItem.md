# Sales__ShoppingCartItem

**Type:** table | **Domain:** Sales | **Rows:** 3 | **SQL name:** `Sales__ShoppingCartItem`

Online shopping cart contents until the order is submitted or cancelled (only test rows here).

**Primary key:** ShoppingCartItemID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ShoppingCartItemID | INTEGER | PK, NOT NULL |  | range 2 .. 5 |
| ShoppingCartID | TEXT | NOT NULL |  | values: '20621' (2), '14951' (1) |
| Quantity | INTEGER | NOT NULL |  | values: 7, 4, 3 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 862 .. 881 |
| DateCreated | TEXT | NOT NULL |  | range 2024-11-08T17:54:07.603000 .. 2024-11-08T17:54:07.603000 |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-11-08T17:54:07.603000 .. 2024-11-08T17:54:07.603000 |

## Relationships

- Sales__ShoppingCartItem.ProductID = Production__Product.ProductID  [declared]
