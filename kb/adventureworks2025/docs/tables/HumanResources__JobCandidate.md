# HumanResources__JobCandidate

**Type:** table | **Domain:** HumanResources | **Rows:** 13 | **SQL name:** `HumanResources__JobCandidate`

Resumes (XML) submitted by job applicants; BusinessEntityID is set if the candidate was hired.

**Primary key:** JobCandidateID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| JobCandidateID | INTEGER | PK, NOT NULL |  | range 1 .. 13 |
| BusinessEntityID | INTEGER | FK -> HumanResources__Employee.BusinessEntityID |  | range 212 .. 274; 84.62% null |
| Resume | TEXT |  |  | values: '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix>...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix/...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix/...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix/...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix/...', '<ns:Resume xmlns:ns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/Resume"><ns:Name><ns:Name.Prefix/...' |
| ModifiedDate | TEXT | NOT NULL |  | range 2007-06-23T00:00:00 .. 2013-12-22T18:32:21.313000 |

## Relationships

- HumanResources__JobCandidate.BusinessEntityID = HumanResources__Employee.BusinessEntityID  [declared]
