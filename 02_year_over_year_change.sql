WITH yearly AS (
  SELECT t.start_year, c.condition_group, COUNT(DISTINCT t.nct_id) AS trials
  FROM trials t
  JOIN conditions c ON t.nct_id = c.nct_id
  WHERE c.condition_group <> 'Other'
  GROUP BY t.start_year, c.condition_group
)
SELECT start_year, condition_group, trials,
       LAG(trials) OVER (PARTITION BY condition_group ORDER BY start_year) AS prev_year,
       ROUND(100.0 * (trials - LAG(trials) OVER (PARTITION BY condition_group ORDER BY start_year))
             / LAG(trials) OVER (PARTITION BY condition_group ORDER BY start_year), 1) AS pct_change
FROM yearly
ORDER BY condition_group, start_year;
