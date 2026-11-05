# Production__ProductModel

**Type:** table | **Domain:** Production | **Rows:** 128 | **SQL name:** `Production__ProductModel`

Product models: a model groups product variants (sizes/colors), e.g. 'Mountain-100'.

**Primary key:** ProductModelID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductModelID | INTEGER | PK, NOT NULL |  | range 1 .. 128 |
| Name | TEXT | NOT NULL |  | e.g. 'All-Purpose Bike Stand', 'Bike Wash', 'Cable Lock' (128 distinct) |
| CatalogDescription | TEXT |  | Detailed product catalog information in XML. | values: '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...', '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...', '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...', '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...', '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...', '<?xml-stylesheet href="ProductDescription.xsl" type="text/xsl"?><p1:ProductDescription xmlns:p1="http://schemas.micro...'; 95.31% null |
| Instructions | TEXT |  | Manufacturing instructions in XML. | values: '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...', '<root xmlns="http://schemas.microsoft.com/sqlserver/2004/07/adventure-works/ProductModelManuInstructions">           ...'; 92.97% null |
| rowguid | TEXT | NOT NULL |  | e.g. '00CE9171-8944-4D49-BA37-485C1D122F5C', '02200AA0-C369-4D77-A67C-75973EFDA81B', '02A562E2-4DFA-4778-BBAC-BBDDCECF99B0' (128 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2015-04-15T16:34:28.980000 .. 2024-04-29T00:00:00 |

## Relationships

- Production__Product.ProductModelID = Production__ProductModel.ProductModelID  [declared]
- Production__ProductModelIllustration.ProductModelID = Production__ProductModel.ProductModelID  [declared]
- Production__ProductModelProductDescriptionCulture.ProductModelID = Production__ProductModel.ProductModelID  [declared]

**Unique indexes:** Production__ProductModel__AK_ProductModel_Name (Name); Production__ProductModel__AK_ProductModel_rowguid (rowguid)
