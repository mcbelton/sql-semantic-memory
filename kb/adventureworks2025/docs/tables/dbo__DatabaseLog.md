# dbo__DatabaseLog

**Type:** table | **Domain:** dbo | **Rows:** 934 | **SQL name:** `dbo__DatabaseLog`

Audit log of DDL changes made to the database (technical, not business data).

**Primary key:** DatabaseLogID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| DatabaseLogID | INTEGER | PK, NOT NULL |  | range 1 .. 934 |
| PostTime | TEXT | NOT NULL |  | range 2025-11-14T13:01:06.967000 .. 2026-04-17T21:27:21.127000 |
| DatabaseUser | TEXT | NOT NULL |  | values: 'dbo' (934) |
| Event | TEXT | NOT NULL |  | values: 'CREATE_EXTENDED_PROPERTY' (538), 'ALTER_TABLE' (117), 'CREATE_INDEX' (95), 'CREATE_TABLE' (70), 'UPDATE_STATISTICS' (22), 'CREATE_VIEW' (20), 'CREATE_FUNCTION' (11), 'CREATE_TRIGGER' (10), 'CREATE_PROCEDURE' (10), 'CREATE_XML_INDEX' (8), 'CREATE_XML_SCHEMA_COLLECTION' (6), 'CREATE_TYPE' (6), 'CREATE_SCHEMA' (5), 'GRANT_DATABASE' (3), 'CREATE_FULLTEXT_INDEX' (3), 'ALTER_XML_SCHEMA_COLLECTION' (3), 'ADD_ROLE_MEMBER' (3), 'ALTER_AUTHORIZATION_DATABASE' (2), 'CREATE_USER' (1), 'CREATE_FULLTEXT_CATALOG' (1) |
| Schema | TEXT |  |  | values: 'Production' (276), 'Sales' (247), 'Person' (151), 'HumanResources' (86), 'Purchasing' (81), 'dbo' (54), 'sys' (21), '' (13); 0.54% null |
| Object | TEXT |  |  | e.g. 'ErrorLog', 'uspPrintError', 'uspLogError'; 473 distinct; 2.36% null |
| TSQL | TEXT | NOT NULL |  | e.g. 'CREATE TABLE [dbo].[ErrorLog](     [ErrorLogID] [int] IDENTITY (1, 1) NOT NULL,     [ErrorTime] [datetime] NOT NULL...', 'ALTER TABLE [dbo].[ErrorLog] WITH CHECK ADD     CONSTRAINT [PK_ErrorLog_ErrorLogID] PRIMARY KEY CLUSTERED     (   ...', ' -- uspPrintError prints error information about the error that caused -- execution to jump to the CATCH block of a...'; 931 distinct |
| XmlEvent | TEXT | NOT NULL |  | e.g. '<EVENT_INSTANCE><EventType>CREATE_TABLE</EventType><PostTime>2025-11-14T13:01:06.930</PostTime><SPID>57</SPID><Server...', '<EVENT_INSTANCE><EventType>ALTER_TABLE</EventType><PostTime>2025-11-14T13:01:06.970</PostTime><SPID>57</SPID><ServerN...', '<EVENT_INSTANCE><EventType>CREATE_PROCEDURE</EventType><PostTime>2025-11-14T13:01:06.973</PostTime><SPID>57</SPID><Se...'; 934 distinct |
