# HumanResources__Department

**Type:** table | **Domain:** HumanResources | **Rows:** 16 | **SQL name:** `HumanResources__Department`

Departments (Engineering, Sales, Production, ...) grouped into department groups.

**Synonyms:** departments, teams, org units

**Primary key:** DepartmentID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| DepartmentID | INTEGER | PK, NOT NULL |  | range 1 .. 16 |
| Name | TEXT | NOT NULL |  | values: 'Document Control', 'Engineering', 'Executive', 'Facilities and Maintenance', 'Finance', 'Human Resources', 'Information Services', 'Marketing', 'Production', 'Production Control', 'Purchasing', 'Quality Assurance', 'Research and Development', 'Sales', 'Shipping and Receiving', 'Tool Design' |
| GroupName | TEXT | NOT NULL | Department group the department belongs to. | values: 'Executive General and Administration' (5), 'Research and Development' (3), 'Sales and Marketing' (2), 'Quality Assurance' (2), 'Manufacturing' (2), 'Inventory Management' (2) |
| ModifiedDate | TEXT | NOT NULL |  | range 2008-04-30T00:00:00 .. 2008-04-30T00:00:00 |

## Relationships

- HumanResources__EmployeeDepartmentHistory.DepartmentID = HumanResources__Department.DepartmentID  [declared]

**Unique indexes:** HumanResources__Department__AK_Department_Name (Name)

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

