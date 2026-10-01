SELECT t.start_year, c.condition_group,
       COUNT(DISTINCT t.nct_id) AS trials
FROM trials t
JOIN conditions c ON t.nct_id = c.nct_id
WHERE c.condition_group <> 'Other'
GROUP BY t.start_year, c.condition_group
ORDER BY t.start_year, c.condition_group;
