# Person__Password

**Type:** table | **Domain:** Person | **Rows:** 19,972 | **SQL name:** `Person__Password`

One-way hashed passwords of people (never select these columns).

**Primary key:** BusinessEntityID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| BusinessEntityID | INTEGER | PK, FK -> Person__Person.BusinessEntityID, NOT NULL |  | range 1 .. 20777 |
| PasswordHash | TEXT | NOT NULL |  | sensitive - values not captured |
| PasswordSalt | TEXT | NOT NULL |  | sensitive - values not captured |
| rowguid | TEXT | NOT NULL |  | e.g. '329EACBE-C883-4F48-B8B6-17AA4627EFFF', 'A4C82398-7466-4FE6-B9EE-CEC34D116F68', 'AC3F4536-BB2E-41C5-B70D-454BE460C1BD'; 19,972 distinct |
| ModifiedDate | TEXT | NOT NULL |  | range 2015-04-15T16:33:33.060000 .. 2025-06-29T00:00:00 |

## Relationships

- Person__Password.BusinessEntityID = Person__Person.BusinessEntityID  [declared]
