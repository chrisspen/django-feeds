/*
2014.7.12 CKS
Shows which domains have the most missing articles.

select * from djangofeeds_articlebydomain
where missing > 0
*/
DROP VIEW IF EXISTS djangofeeds_articlebydomain CASCADE;
CREATE OR REPLACE VIEW djangofeeds_articlebydomain
AS
SELECT  m.*,
        m.missing::float/m.total AS missing_ratio
FROM (
SELECT  EXTRACT(year FROM date_published) AS year,
        EXTRACT(month FROM date_published) AS month,
        SUBSTRING(link FROM 'http://([^/]+)') AS domain,
        COUNT(*) AS total,
        COUNT(CASE WHEN article_content IS NULL THEN 1 ELSE NULL END) AS missing
FROM    djangofeeds_post as p
GROUP BY year, month, domain
) AS m
ORDER BY year DESC, month DESC, missing_ratio DESC;
