/*
2014.3.9 CKS
Aggregates article extraction statistics for the post table on a monthly basis.
*/
DROP VIEW IF EXISTS djangofeeds_article CASCADE;
CREATE OR REPLACE VIEW djangofeeds_article
AS
SELECT  m.*,
        m.has_article/m.total::float AS ratio_extracted
FROM (
    SELECT  CONCAT(CAST(EXTRACT(year FROM p.date_published) AS VARCHAR), '-', CAST(EXTRACT(month from p.date_published) AS VARCHAR)) AS id,
            EXTRACT(year FROM p.date_published) AS year,
            EXTRACT(month from p.date_published) AS month,
            COUNT(id) AS total,
            COUNT(CASE WHEN p.article_content IS NOT NULL AND p.article_content != '' THEN 1 ELSE NULL END) AS has_article
    FROM    djangofeeds_post AS p
    GROUP BY
            year, month
) AS m;