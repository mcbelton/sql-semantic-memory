# Production__Document

**Type:** table | **Domain:** Production | **Rows:** 12 | **SQL name:** `Production__Document`

Product maintenance documents (hierarchical folders and documents).

**Primary key:** DocumentNode

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| DocumentNode | BLOB | PK, NOT NULL |  |  |
| DocumentLevel | INTEGER |  |  | values: 2 (8), 1 (3), 0 (1) |
| Title | TEXT | NOT NULL |  | values: 'Seat Assembly', 'Repair and Service Guidelines', 'Overview', 'Maintenance', 'Lubrication Maintenance', 'Introduction 1', 'Installing Replacement Pedals', 'Front Reflector Bracket and Reflector Assembly 3', 'Front Reflector Bracket Installation', 'Documents', 'Crank Arm and Tire Maintenance', 'Assembly' |
| Owner | INTEGER | FK -> HumanResources__Employee.BusinessEntityID, NOT NULL | Employee who controls the document. | range 217 .. 220 |
| FolderFlag | INTEGER | NOT NULL | Folder or document. | codes: 0=Document, 1=Folder; values: 0 (8), 1 (4) |
| FileName | TEXT | NOT NULL |  | values: 'Assembly', 'Crank Arm and Tire Maintenance.doc', 'Documents', 'Front Reflector Bracket Installation.doc', 'Front Reflector Bracket and Reflector Assembly 3.doc', 'Installing Replacement Pedals.doc', 'Introduction 1.doc', 'Lubrication Maintenance.doc', 'Maintenance', 'Overview', 'Repair and Service Guidelines.doc', 'Seat Assembly.doc' |
| FileExtension | TEXT | NOT NULL |  | values: '.doc' (8), '' (4) |
| Revision | TEXT | NOT NULL |  | values: '0    ' (7), '8    ' (1), '4    ' (1), '3    ' (1), '2    ' (1), '1    ' (1) |
| ChangeNumber | INTEGER | NOT NULL |  | values: 0 (5), 55 (1), 32 (1), 28 (1), 25 (1), 15 (1), 11 (1), 8 (1) |
| Status | INTEGER | NOT NULL | Document status. | codes: 1=Pending approval, 2=Approved, 3=Obsolete; values: 2 (10), 1 (2) |
| DocumentSummary | TEXT |  |  | values: 'Worn or damaged seats can be easily replaced following these simple instructions.  Instructions are applicable to the...', 'Reflectors are vital safety components of your bicycle. Always ensure your front and back reflectors are clean and in...', 'It is important that you maintain your bicycle and keep it in good repair. Detailed repair and service guidelines are...', 'Guidelines and recommendations for lubricating the required components of your Adventure Works Cycles bicycle. Compon...', 'Detailed instructions for replacing pedals with Adventure Works Cycles replacement pedals.  Instructions are applicab...'; 58.33% null |
| Document | BLOB |  |  |  |
| rowguid | TEXT | NOT NULL |  | values: '26A266F1-1D23-40E2-AF48-6AB8D954FE37', '27CF33AF-C338-4842-966C-75CA11AAA6A3', '2A8BD319-36FB-4FBA-9E07-E303839F1974', '48265174-8451-4967-973A-639C2276CFAF', '5184D96A-EE8C-499A-9316-625496784DE6', '52F6BE23-5363-4D93-96AE-F714B851E52C', '79D41FE8-39D7-4591-9A05-285A3E1AAFCB', '7ED4DEF5-D5BB-4818-8748-5BB5F8315FA2', '7EE72C7E-9800-44C1-B82D-6E34E8289CA1', '82F61D73-0BF5-44FF-AB99-DD73AEE9B9CC', 'D11B82B0-EB40-4A66-8193-15F765A61F05', 'F4F544AE-381A-4323-9A59-F5A629E21F46' |
| ModifiedDate | TEXT | NOT NULL |  | range 2017-12-13T13:58:03.943000 .. 2024-05-29T00:00:00 |

## Relationships

- Production__Document.Owner = HumanResources__Employee.BusinessEntityID  [declared]
- Production__ProductDocument.DocumentNode = Production__Document.DocumentNode  [declared]

**Unique indexes:** Production__Document__AK_Document_DocumentLevel_DocumentNode (DocumentLevel, DocumentNode); Production__Document__AK_Document_rowguid (rowguid); Production__Document__UQ__Document__F73921F7248A8848 (rowguid)
