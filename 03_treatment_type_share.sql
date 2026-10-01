WITH typed AS (
  SELECT DISTINCT t.nct_id, t.start_year, i.intervention_type
  FROM trials t
  JOIN interventions i ON t.nct_id = i.nct_id
  WHERE t.in_scope = 1
)
SELECT start_year, intervention_type, COUNT(*) AS trials,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY start_year), 1) AS pct_of_year
FROM typed
GROUP BY start_year, intervention_type
ORDER BY start_year, trials DESC;
