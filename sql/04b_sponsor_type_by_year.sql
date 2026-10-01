SELECT t.start_year, t.sponsor_class, COUNT(*) AS trials,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY t.start_year), 1) AS pct_of_year
FROM trials t
WHERE t.in_scope = 1
GROUP BY t.start_year, t.sponsor_class
ORDER BY t.start_year, trials DESC;
