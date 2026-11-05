# HumanResources__Employee

**Type:** table | **Domain:** HumanResources | **Rows:** 290 | **SQL name:** `HumanResources__Employee`

Employees: job title, hire date, demographics, hourly/salaried, vacation and sick leave. Names are in Person__Person (same BusinessEntityID).

**Synonyms:** employees, staff, workers, personnel, headcount

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL | Primary key; same id as Person__Person. | range 1 .. 290 |
| NationalIDNumber | TEXT | NOT NULL | National identification number such as a social security number. | sensitive - values not captured |
| LoginID | TEXT | NOT NULL | Network login. | sensitive - values not captured |
| OrganizationNode | BLOB |  | Position in the corporate hierarchy (binary hierarchyid; use OrganizationLevel). |  |
| OrganizationLevel | INTEGER |  | Depth in the corporate hierarchy (1 = reports to the CEO). | values: 4 (190), 3 (66), 2 (27), 1 (6); 0.34% null |
| JobTitle | TEXT | NOT NULL | Work title such as Buyer or Sales Representative. | values: 'Production Technician - WC60' (26), 'Production Technician - WC50' (26), 'Production Technician - WC40' (26), 'Production Technician - WC30' (25), 'Production Technician - WC20' (22), 'Production Technician - WC10' (17), 'Production Technician - WC45' (15), 'Sales Representative' (14), 'Buyer' (9), 'Marketing Specialist' (5), 'Scheduling Assistant' (4), 'Quality Assurance Technician' (4), 'Janitor' (4), 'Application Specialist' (4), 'Stocker' (3), 'Production Supervisor - WC60' (3), 'Production Supervisor - WC50' (3), 'Production Supervisor - WC45' (3), 'Production Supervisor - WC40' (3), 'Production Supervisor - WC30' (3), ... (67 distinct) |
| BirthDate | TEXT | NOT NULL | Date of birth. | sensitive - values not captured |
| MaritalStatus | TEXT | NOT NULL | Marital status. | codes: M=Married, S=Single; values: 'M' (146), 'S' (144) |
| Gender | TEXT | NOT NULL | Gender. | codes: M=Male, F=Female; values: 'M' (206), 'F' (84) |
| HireDate | TEXT | NOT NULL | Date the employee was hired. | range 2006-06-30 .. 2013-05-30 |
| SalariedFlag | TEXT | NOT NULL | Job classification. | codes: 0=Hourly, not exempt from collective bargaining, 1=Salaried, exempt from collective bargaining; values: '0' (238), '1' (52) |
| VacationHours | INTEGER | NOT NULL | Number of available vacation hours. | range 0 .. 99, avg 50.6138 |
| SickLeaveHours | INTEGER | NOT NULL | Number of available sick leave hours. | range 20 .. 80, avg 45.3069 |
| CurrentFlag | TEXT | NOT NULL | Employment status. | codes: 0=Inactive, 1=Active; values: '1' (290) |
| rowguid | TEXT | NOT NULL |  | e.g. '00027A8C-C2F8-4A31-ABA8-8A203638B8F1', '01B119A2-2AF3-4775-818E-B421FECB07A7', '01BCCE22-D63A-4C3F-9BA8-D3D5A4C3BD52'; 290 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2014-06-30T00:00:00 .. 2014-12-26T09:17:08.637000 |

## Relationships

- HumanResources__Employee.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
- HumanResources__EmployeeDepartmentHistory.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
- HumanResources__EmployeePayHistory.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
- HumanResources__JobCandidate.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
- Production__Document.Owner = HumanResources__Employee.BusinessEntityID  [declared]
- Purchasing__PurchaseOrderHeader.EmployeeID = HumanResources__Employee.BusinessEntityID  [declared]
- Sales__SalesPerson.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]

**Unique indexes:** HumanResources__Employee__AK_Employee_LoginID (LoginID); HumanResources__Employee__AK_Employee_NationalIDNumber (NationalIDNumber); HumanResources__Employee__AK_Employee_rowguid (rowguid)

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

