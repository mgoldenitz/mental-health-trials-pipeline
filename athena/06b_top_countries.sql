SELECT s.country, COUNT(DISTINCT t.nct_id) AS trials,
       ROUND(100.0E0 * COUNT(DISTINCT t.nct_id)
             / (SELECT COUNT(*) FROM trials WHERE start_year BETWEEN 2010 AND 2025), 1) AS pct
FROM trials t JOIN sites s ON t.nct_id = s.nct_id
WHERE t.start_year BETWEEN 2010 AND 2025
GROUP BY s.country ORDER BY trials DESC LIMIT 10;
