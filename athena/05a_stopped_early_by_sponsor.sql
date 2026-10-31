SELECT sponsor_class,
       COUNT(*) AS ended_trials,
       COUNT_IF(overall_status = 'COMPLETED') AS completed,
       COUNT_IF(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED')) AS stopped_early,
       ROUND(100.0E0 * COUNT_IF(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED'))
             / COUNT(*), 1) AS pct_stopped_early
FROM trials
WHERE start_year BETWEEN 2010 AND 2025
  AND overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED')
GROUP BY sponsor_class
ORDER BY ended_trials DESC;
