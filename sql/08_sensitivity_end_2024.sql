-- Sensitivity check: do the growth findings hold if the window ends in 2024?
-- 2025 starts are still being registered and updated, so 2025 counts may run low.
-- Growth = trials started in the late three years / trials started in 2010-12.
WITH per_group AS (
  SELECT c.condition_group,
         COUNT(DISTINCT CASE WHEN t.start_year BETWEEN 2010 AND 2012 THEN t.nct_id END) AS trials_2010_12,
         COUNT(DISTINCT CASE WHEN t.start_year BETWEEN 2023 AND 2025 THEN t.nct_id END) AS trials_2023_25,
         COUNT(DISTINCT CASE WHEN t.start_year BETWEEN 2022 AND 2024 THEN t.nct_id END) AS trials_2022_24
  FROM trials t
  JOIN conditions c ON t.nct_id = c.nct_id
  WHERE c.condition_group <> 'Other'
  GROUP BY c.condition_group
)
SELECT condition_group, trials_2010_12, trials_2023_25, trials_2022_24,
       ROUND(1.0 * trials_2023_25 / trials_2010_12, 2) AS growth_to_2025,
       ROUND(1.0 * trials_2022_24 / trials_2010_12, 2) AS growth_to_2024
FROM per_group
ORDER BY growth_to_2025 DESC;
