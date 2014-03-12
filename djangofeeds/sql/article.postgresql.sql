/*
2014.3.9 CKS
Aggregates article extraction statistics for the post table on a monthly basis.
*/
DROP VIEW IF EXISTS djangofeeds_article CASCADE;
CREATE OR REPLACE VIEW djangofeeds_article
AS
SELECT  CONCAT(CAST(m.year AS VARCHAR), '-', CAST(m.month AS VARCHAR)) AS id,
        m.*,
        m.has_article/m.total::float AS ratio_extracted
FROM (
    SELECT  EXTRACT(year FROM p.date_published)::int AS year,
            EXTRACT(month from p.date_published)::int AS month,
            COUNT(id) AS total,
            AVG(p.article_content_length)::int as mean_length,
            COUNT(CASE WHEN p.article_content IS NOT NULL AND p.article_content != '' THEN 1 ELSE NULL END) AS has_article
    FROM    djangofeeds_post AS p
    GROUP BY
            year, month
) AS m;