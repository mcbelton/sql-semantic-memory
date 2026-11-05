# HumanResources__EmployeeDepartmentHistory

**Type:** table | **Domain:** HumanResources | **Rows:** 296 | **SQL name:** `HumanResources__EmployeeDepartmentHistory`

Department and shift assignments of employees over time. EndDate NULL = the employee's current department.

**Primary key:** BusinessEntityID, StartDate, DepartmentID, ShiftID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> HumanResources__Employee.BusinessEntityID, NOT NULL |  | range 1 .. 290 |
| DepartmentID | INTEGER | PK, FK -> HumanResources__Department.DepartmentID, NOT NULL |  | range 1 .. 16 |
| ShiftID | INTEGER | PK, FK -> HumanResources__Shift.ShiftID, NOT NULL | Work shift. Join HumanResources__Shift. | range 1 .. 3 |
| StartDate | TEXT | PK, NOT NULL |  | range 2006-06-30 .. 2013-11-14 |
| EndDate | TEXT |  | Date the employee left the department; NULL = current department. | range 2009-07-14 .. 2013-11-13; 97.97% null |
| ModifiedDate | TEXT | NOT NULL |  | range 2006-06-29T00:00:00 .. 2013-11-13T00:00:00 |

## Relationships

- HumanResources__EmployeeDepartmentHistory.DepartmentID = HumanResources__Department.DepartmentID  [declared]
- HumanResources__EmployeeDepartmentHistory.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
- HumanResources__EmployeeDepartmentHistory.ShiftID = HumanResources__Shift.ShiftID  [declared]

## Business definitions

- **Current department**: The HumanResources__EmployeeDepartmentHistory row with EndDate IS NULL.

## Example queries

**Current number of employees per department**

```sql
SELECT d.GroupName, d.Name AS department, COUNT(*) AS employees
FROM HumanResources__EmployeeDepartmentHistory edh
JOIN HumanResources__Department d ON d.DepartmentID = edh.DepartmentID
WHERE edh.EndDate IS NULL
GROUP BY d.GroupName, d.Name
ORDER BY employees DESC;
```

**Current pay rate of each employee with job title and department**

```sql
WITH latest_pay AS (
  SELECT BusinessEntityID, Rate,
         ROW_NUMBER() OVER (PARTITION BY BusinessEntityID ORDER BY RateChangeDate DESC) AS rn
  FROM HumanResources__EmployeePayHistory
)
SELECT p.FirstName || ' ' || p.LastName AS employee, e.JobTitle, d.Name AS department, lp.Rate AS hourly_rate
FROM HumanResources__Employee e
JOIN Person__Person p ON p.BusinessEntityID = e.BusinessEntityID
JOIN latest_pay lp ON lp.BusinessEntityID = e.BusinessEntityID AND lp.rn = 1
JOIN HumanResources__EmployeeDepartmentHistory edh ON edh.BusinessEntityID = e.BusinessEntityID AND edh.EndDate IS NULL
JOIN HumanResources__Department d ON d.DepartmentID = edh.DepartmentID
ORDER BY lp.Rate DESC;
```

