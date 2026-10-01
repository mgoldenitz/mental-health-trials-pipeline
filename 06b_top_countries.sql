SELECT s.country, COUNT(DISTINCT t.nct_id) AS trials,
       ROUND(100.0 * COUNT(DISTINCT t.nct_id) / (SELECT COUNT(*) FROM trials WHERE in_scope = 1), 1) AS pct
FROM trials t JOIN sites s ON t.nct_id = s.nct_id
WHERE t.in_scope = 1
GROUP BY s.country ORDER BY trials DESC LIMIT 10;
