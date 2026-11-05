# HumanResources__Shift

**Type:** table | **Domain:** HumanResources | **Rows:** 3 | **SQL name:** `HumanResources__Shift`

Work shifts (Day, Evening, Night) with start and end times.

**Primary key:** ShiftID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ShiftID | INTEGER | PK, NOT NULL |  | range 1 .. 3 |
| Name | TEXT | NOT NULL |  | values: 'Day', 'Evening', 'Night' |
| StartTime | TEXT | NOT NULL |  | values: '07:00:00', '15:00:00', '23:00:00' |
| EndTime | TEXT | NOT NULL |  | values: '23:00:00', '15:00:00', '07:00:00' |
| ModifiedDate | TEXT | NOT NULL |  | range 2008-04-30T00:00:00 .. 2008-04-30T00:00:00 |

## Relationships

- HumanResources__EmployeeDepartmentHistory.ShiftID = HumanResources__Shift.ShiftID  [declared]

**Unique indexes:** HumanResources__Shift__AK_Shift_Name (Name); HumanResources__Shift__AK_Shift_StartTime_EndTime (StartTime, EndTime)
