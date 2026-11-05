# HumanResources__EmployeePayHistory

**Type:** table | **Domain:** HumanResources | **Rows:** 316 | **SQL name:** `HumanResources__EmployeePayHistory`

Pay rate changes per employee. The current rate is the row with the latest RateChangeDate.

**Synonyms:** salaries, pay rates, wages, compensation

**Primary key:** BusinessEntityID, RateChangeDate

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> HumanResources__Employee.BusinessEntityID, NOT NULL |  | range 1 .. 290 |
| RateChangeDate | TEXT | PK, NOT NULL | Date the rate became effective. | range 2006-06-30T00:00:00 .. 2013-07-14T00:00:00 |
| Rate | NUMERIC | NOT NULL | Hourly pay rate. | range 6.5 .. 125.5, avg 17.7588 |
| PayFrequency | INTEGER | NOT NULL | Pay frequency. | codes: 1=Paid monthly, 2=Paid biweekly; values: 1 (180), 2 (136) |
| ModifiedDate | TEXT | NOT NULL |  | range 2007-11-21T00:00:00 .. 2014-06-30T00:00:00 |

## Relationships

- HumanResources__EmployeePayHistory.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]

## Business definitions

- **Current pay rate**: Per employee, the HumanResources__EmployeePayHistory row with the latest RateChangeDate (ROW_NUMBER() OVER (PARTITION BY BusinessEntityID ORDER BY RateChangeDate DESC) = 1).

## Example queries

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

