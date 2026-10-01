WITH counts AS (
  SELECT c.condition_group, t.sponsor_name, t.sponsor_class,
         COUNT(DISTINCT t.nct_id) AS trials
  FROM trials t
  JOIN conditions c ON t.nct_id = c.nct_id
  WHERE c.condition_group <> 'Other'
  GROUP BY c.condition_group, t.sponsor_name, t.sponsor_class
),
ranked AS (
  SELECT *, RANK() OVER (PARTITION BY condition_group ORDER BY trials DESC) AS rnk
  FROM counts
)
SELECT * FROM ranked WHERE rnk <= 5
ORDER BY condition_group, rnk;
