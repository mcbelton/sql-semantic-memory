# dbo__ErrorLog

**Type:** table | **Domain:** dbo | **Rows:** 0 | **SQL name:** `dbo__ErrorLog`

Errors captured by the database's error-handling procedure (technical, empty).

**Primary key:** ErrorLogID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ErrorLogID | INTEGER | PK, NOT NULL |  |  |
| ErrorTime | TEXT | NOT NULL |  | 0 distinct |
| UserName | TEXT | NOT NULL |  | sensitive - values not captured |
| ErrorNumber | INTEGER | NOT NULL |  |  |
| ErrorSeverity | INTEGER |  |  |  |
| ErrorState | INTEGER |  |  |  |
| ErrorProcedure | TEXT |  |  | 0 distinct |
| ErrorLine | INTEGER |  |  |  |
| ErrorMessage | TEXT | NOT NULL |  | 0 distinct |
