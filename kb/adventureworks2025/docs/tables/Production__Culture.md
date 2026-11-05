# Production__Culture

**Type:** table | **Domain:** Production | **Rows:** 8 | **SQL name:** `Production__Culture`

Languages in which product descriptions are stored. CultureID is padded to 6 characters ('en    ').

**Primary key:** CultureID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| CultureID | TEXT | PK, NOT NULL |  | values: '      ', 'ar    ', 'en    ', 'es    ', 'fr    ', 'he    ', 'th    ', 'zh-cht' |
| Name | TEXT | NOT NULL |  | values: 'Arabic', 'Chinese', 'English', 'French', 'Hebrew', 'Invariant Language (Invariant Country)', 'Spanish', 'Thai' |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-04-30T00:00:00 .. 2019-04-30T00:00:00 |

## Relationships

- Production__ProductModelProductDescriptionCulture.CultureID = Production__Culture.CultureID  [declared]

**Unique indexes:** Production__Culture__AK_Culture_Name (Name)
