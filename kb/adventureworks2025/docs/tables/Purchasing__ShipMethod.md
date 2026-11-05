# Purchasing__ShipMethod

**Type:** table | **Domain:** Purchasing | **Rows:** 5 | **SQL name:** `Purchasing__ShipMethod`

Shipping companies/methods used for sales and purchase orders.

**Primary key:** ShipMethodID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ShipMethodID | INTEGER | PK, NOT NULL |  | range 1 .. 5 |
| Name | TEXT | NOT NULL |  | values: 'CARGO TRANSPORT 5', 'OVERNIGHT J-FAST', 'OVERSEAS - DELUXE', 'XRQ - TRUCK GROUND', 'ZY - EXPRESS' |
| ShipBase | NUMERIC | NOT NULL | Minimum shipping charge. | range 3.95 .. 29.95, avg 14.958 |
| ShipRate | NUMERIC | NOT NULL | Shipping charge per pound. | range 0.99 .. 2.99, avg 1.75 |
| rowguid | TEXT | NOT NULL |  | values: '107E8356-E7A8-463D-B60C-079FFF467F3F', '22F4E461-28CF-4ACE-A980-F686CF112EC8', '3455079B-F773-4DC6-8F1E-2A58649C4AB8', '6BE756D9-D7BE-4463-8F2C-AE60C710D606', 'B166019A-B134-4E76-B957-2B0490C610ED' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Purchasing__PurchaseOrderHeader.ShipMethodID = Purchasing__ShipMethod.ShipMethodID  [declared]
- Sales__SalesOrderHeader.ShipMethodID = Purchasing__ShipMethod.ShipMethodID  [declared]

**Unique indexes:** Purchasing__ShipMethod__AK_ShipMethod_Name (Name); Purchasing__ShipMethod__AK_ShipMethod_rowguid (rowguid)
