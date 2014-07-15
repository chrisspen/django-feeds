/*
2014.7.12 CKS
Shows which domains have the most missing articles.

select * from djangofeeds_articlebydomain
where missing > 0
order by missing desc
*/
DROP VIEW IF EXISTS djangofeeds_articlebydomain CASCADE;
CREATE OR REPLACE VIEW djangofeeds_articlebydomain
AS
SELECT  CONCAT(CAST(m.year AS VARCHAR), '-', CAST(m.month AS VARCHAR), '-', CAST(m.domain AS VARCHAR)) AS id,
        m.*,
        m.missing::float/m.total AS missing_ratio,
        m.missing_without_error::float/m.total AS missing_without_error_ratio,
        m.missing_without_error_or_success::float/m.total AS missing_without_error_or_success_ratio
FROM (
SELECT  EXTRACT(year FROM date_published)::int AS year,
        EXTRACT(month FROM date_published)::int AS month,
        SUBSTRING(link FROM 'http://([^/]+)') AS domain,
        COUNT(*) AS total,
        COUNT(CASE WHEN article_content IS NULL THEN 1 ELSE NULL END) AS missing,
        COUNT(CASE WHEN article_content IS NULL AND article_content_error_code IS NULL THEN 1 ELSE NULL END) AS missing_without_error,
        COUNT(CASE WHEN article_content IS NULL AND article_content_error_code IS NULL AND article_content_success IS NULL THEN 1 ELSE NULL END) AS missing_without_error_or_success
FROM    djangofeeds_post as p
GROUP BY year, month, domain
) AS m
ORDER BY year DESC, month DESC, missing_ratio DESC;
