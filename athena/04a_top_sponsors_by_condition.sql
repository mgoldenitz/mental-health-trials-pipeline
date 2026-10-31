WITH counts AS (
  SELECT c.condition_group, t.sponsor_name, t.sponsor_class,
         COUNT(DISTINCT t.nct_id) AS trials
  FROM trials t
  JOIN conditions c ON t.nct_id = c.nct_id
  WHERE t.start_year BETWEEN 2010 AND 2025
  GROUP BY c.condition_group, t.sponsor_name, t.sponsor_class
),
ranked AS (
  SELECT counts.*, RANK() OVER (PARTITION BY condition_group ORDER BY trials DESC) AS rnk
  FROM counts
)
SELECT * FROM ranked WHERE rnk <= 5
ORDER BY condition_group, rnk;
