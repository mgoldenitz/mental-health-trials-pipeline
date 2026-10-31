SELECT c.condition_group,
       COUNT(DISTINCT c.nct_id) AS all_trials,
       COUNT(DISTINCT CASE WHEN s.country = 'Canada' THEN c.nct_id END) AS with_canadian_site,
       ROUND(100.0E0 * COUNT(DISTINCT CASE WHEN s.country = 'Canada' THEN c.nct_id END)
             / COUNT(DISTINCT c.nct_id), 1) AS pct_canada
FROM conditions c
JOIN trials t ON c.nct_id = t.nct_id
LEFT JOIN sites s ON c.nct_id = s.nct_id
WHERE t.start_year BETWEEN 2010 AND 2025
GROUP BY c.condition_group
ORDER BY pct_canada DESC;
