WITH yearly AS (
  SELECT t.start_year, i.psychedelic_class, COUNT(DISTINCT t.nct_id) AS trials
  FROM trials t
  JOIN interventions i ON t.nct_id = i.nct_id
  WHERE i.psychedelic_class IS NOT NULL AND t.in_scope = 1
  GROUP BY t.start_year, i.psychedelic_class
)
SELECT start_year, psychedelic_class, trials,
       SUM(trials) OVER (PARTITION BY psychedelic_class ORDER BY start_year) AS running_total
FROM yearly
ORDER BY psychedelic_class, start_year;
