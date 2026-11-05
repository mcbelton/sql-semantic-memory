# Production__ProductPhoto

**Type:** table | **Domain:** Production | **Rows:** 101 | **SQL name:** `Production__ProductPhoto`

Product images (thumbnail and large photo blobs).

**Primary key:** ProductPhotoID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductPhotoID | INTEGER | PK, NOT NULL |  | range 1 .. 181 |
| ThumbNailPhoto | BLOB |  |  |  |
| ThumbnailPhotoFileName | TEXT |  |  | e.g. 'wheel_small.gif', 'water_bottle_small.gif', 'water_bottle_cage_small.gif' (101 distinct) |
| LargePhoto | BLOB |  |  |  |
| LargePhotoFileName | TEXT |  |  | e.g. 'wheel_large.gif', 'water_bottle_large.gif', 'water_bottle_cage_large.gif' (101 distinct) |
| ModifiedDate | TEXT | NOT NULL |  | range 2019-03-31T00:00:00 .. 2024-04-29T00:00:00 |

## Relationships

- Production__ProductProductPhoto.ProductPhotoID = Production__ProductPhoto.ProductPhotoID  [declared]
