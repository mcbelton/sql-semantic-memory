# Production__Location

**Type:** table | **Domain:** Production | **Rows:** 14 | **SQL name:** `Production__Location`

Inventory and manufacturing locations (work centers such as Frame Welding, Paint, Final Assembly, and storage areas).

**Primary key:** LocationID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| LocationID | INTEGER | PK, NOT NULL |  | range 1 .. 60 |
| Name | TEXT | NOT NULL |  | values: 'Debur and Polish', 'Final Assembly', 'Finished Goods Storage', 'Frame Forming', 'Frame Welding', 'Metal Storage', 'Miscellaneous Storage', 'Paint', 'Paint Shop', 'Paint Storage', 'Sheet Metal Racks', 'Specialized Paint', 'Subassembly', 'Tool Crib' |
| CostRate | NUMERIC | NOT NULL | Standard hourly cost of the manufacturing location. | values: 0 (7), 12.25 (2), 25 (1), 22.5 (1), 18 (1), 15.75 (1), 14.5 (1) |
| Availability | NUMERIC | NOT NULL | Work capacity (in hours) of the manufacturing location. | values: 0 (7), 120 (4), 108 (1), 96 (1), 80 (1) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__ProductInventory.LocationID = Production__Location.LocationID  [declared]
- Production__WorkOrderRouting.LocationID = Production__Location.LocationID  [declared]

**Unique indexes:** Production__Location__AK_Location_Name (Name)
