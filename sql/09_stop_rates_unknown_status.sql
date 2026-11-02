-- Stop rates with the UNKNOWN-status trials handled three ways.
-- ClinicalTrials.gov marks a trial UNKNOWN when its record has not been verified
-- for 2 years past its completion date. The published rate (05a) leaves them out.
--   published:      ended trials only (COMPLETED, TERMINATED, WITHDRAWN, SUSPENDED)
--   unknown_as_completed: lower bound, every UNKNOWN trial counted as finished
--   unknown_as_stopped:   upper bound, every UNKNOWN trial counted as stopped early
SELECT sponsor_class,
       SUM(overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED')) AS ended_trials,
       SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED')) AS stopped_early,
       SUM(overall_status = 'UNKNOWN') AS unknown_status,
       ROUND(100.0 * SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED'))
             / SUM(overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED')), 1) AS pct_published,
       ROUND(100.0 * SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED'))
             / SUM(overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED','UNKNOWN')), 1) AS pct_unknown_as_completed,
       ROUND(100.0 * SUM(overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED','UNKNOWN'))
             / SUM(overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED','UNKNOWN')), 1) AS pct_unknown_as_stopped
FROM trials
WHERE in_scope = 1
GROUP BY sponsor_class
HAVING SUM(overall_status IN ('COMPLETED','TERMINATED','WITHDRAWN','SUSPENDED','UNKNOWN')) > 0
ORDER BY ended_trials DESC;
