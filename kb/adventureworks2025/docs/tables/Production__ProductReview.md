# Production__ProductReview

**Type:** table | **Domain:** Production | **Rows:** 4 | **SQL name:** `Production__ProductReview`

Customer reviews of products.

**Synonyms:** reviews, ratings, feedback

**Primary key:** ProductReviewID

## Columns

| Column | Type | Keys / flags | Description | Data profile |
|---|---|---|---|---|
| ProductReviewID | INTEGER | PK, NOT NULL |  | range 1 .. 4 |
| ProductID | INTEGER | FK -> Production__Product.ProductID, NOT NULL |  | range 709 .. 937 |
| ReviewerName | TEXT | NOT NULL |  | values: 'Laura Norman', 'John Smith', 'Jill', 'David' |
| ReviewDate | TEXT | NOT NULL |  | range 2024-09-17T00:00:00 .. 2024-11-14T00:00:00 |
| EmailAddress | TEXT | NOT NULL |  | sensitive - values not captured |
| Rating | INTEGER | NOT NULL | Product rating given by the reviewer, 1 (lowest) to 5 (highest). | values: 5 (2), 4 (1), 2 (1) |
| Comments | TEXT |  | Review text. | values: 'The Road-550-W from Adventure Works Cycles is everything it''s advertised to be. Finally, a quality bike that is actua...', 'Maybe it''s just because I''m new to mountain biking, but I had a terrible time getting use to these pedals. In my firs...', 'I can''t believe I''m singing the praises of a pair of socks, but I just came back from a grueling 3-day ride and these...', 'A little on the heavy side, but overall the entry/exit is easy in all conditions. I''ve used these pedals for more tha...' |
| ModifiedDate | TEXT | NOT NULL |  | range 2024-09-17T00:00:00 .. 2024-11-14T00:00:00 |

## Relationships

- Production__ProductReview.ProductID = Production__Product.ProductID  [declared]
