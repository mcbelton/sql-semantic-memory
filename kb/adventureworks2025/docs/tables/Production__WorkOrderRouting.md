# Production__WorkOrderRouting

**Type:** table | **Domain:** Production | **Rows:** 67,131 | **SQL name:** `Production__WorkOrderRouting`

Manufacturing steps (routing) of each work order: location, planned vs actual dates, hours and cost.

**Primary key:** WorkOrderID, ProductID, OperationSequence

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| WorkOrderID | INTEGER | PK, FK -> Production__WorkOrder.WorkOrderID, NOT NULL |  | range 13 .. 72587 |
| ProductID | INTEGER | PK, FK -> Production__Product.ProductID, NOT NULL |  | range 514 .. 999 |
| OperationSequence | INTEGER | PK, NOT NULL | Manufacturing process step sequence. | range 1 .. 7 |
| LocationID | INTEGER | FK -> Production__Location.LocationID, NOT NULL | Manufacturing location where the step is done. | range 10 .. 60 |
| ScheduledStartDate | TEXT | NOT NULL |  | range 2022-06-02T00:00:00 .. 2025-06-01T00:00:00 |
| ScheduledEndDate | TEXT | NOT NULL |  | range 2022-06-13T00:00:00 .. 2025-06-12T00:00:00 |
| ActualStartDate | TEXT |  |  | range 2022-06-02T00:00:00 .. 2025-06-16T00:00:00 |
| ActualEndDate | TEXT |  |  | range 2022-06-14T00:00:00 .. 2025-06-27T00:00:00 |
| ActualResourceHrs | NUMERIC |  | Number of manufacturing hours used. | values: 3 (30,107), 4 (18,554), 4.1 (9,567), 3.5 (5,923), 2 (1,490), 1 (1,490) |
| PlannedCost | NUMERIC | NOT NULL | Estimated manufacturing cost. | values: 36.75 (30,107), 49 (18,554), 92.25 (9,567), 87.5 (5,923), 14.5 (1,490), 31.5 (816), 36 (674) |
| ActualCost | NUMERIC |  | Actual manufacturing cost. | values: 36.75 (30,107), 49 (18,554), 92.25 (9,567), 87.5 (5,923), 14.5 (1,490), 31.5 (816), 36 (674) |
| ModifiedDate | TEXT | NOT NULL |  | range 2022-06-14T00:00:00 .. 2025-06-27T00:00:00 |

## Relationships

- Production__WorkOrderRouting.LocationID = Production__Location.LocationID  [declared]
- Production__WorkOrderRouting.WorkOrderID = Production__WorkOrder.WorkOrderID  [declared]
- Production__WorkOrderRouting.ProductID = Production__Product.ProductID  [inferred]
