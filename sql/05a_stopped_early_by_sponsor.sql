SELECT sponsor_class,
       COUNT(*) AS ended_trials,
       SUM(overall_status = 'COMPLETED') AS completed,
       SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED')) AS stopped_early,
       ROUND(100.0 * SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED'))
             / COUNT(*), 1) AS pct_stopped_early
FROM trials
WHERE in_scope = 1
  AND overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED')
GROUP BY sponsor_class
ORDER BY ended_trials DESC;
