WITH reasons AS (
  SELECT sponsor_class, LOWER(why_stopped) AS r
  FROM trials
  WHERE in_scope = 1
    AND overall_status IN ('TERMINATED','WITHDRAWN','SUSPENDED')
    AND TRIM(COALESCE(why_stopped, '')) <> ''
),
grouped AS (
  SELECT sponsor_class,
    CASE
      WHEN r LIKE '%covid%' OR r LIKE '%pandemic%' OR r LIKE '%coronavirus%' THEN 'COVID-19'
      WHEN r LIKE '%efficacy%' OR r LIKE '%futility%' OR r LIKE '%interim analys%' THEN 'Efficacy / futility'
      WHEN r LIKE '%sponsor decision%' OR r LIKE '%business%' OR r LIKE '%strategic%'
        OR r LIKE '%portfolio%' OR r LIKE '%company decision%' OR r LIKE '%program%' THEN 'Sponsor / business decision'
      WHEN r LIKE '%fund%' OR r LIKE '%budget%' OR r LIKE '%financ%' THEN 'Funding'
      WHEN r LIKE '%recruit%' OR r LIKE '%enrol%' OR r LIKE '%accrual%'
        OR r LIKE '%participant%' OR r LIKE '%subject%' OR r LIKE '%patient%' THEN 'Recruitment'
      WHEN r LIKE '%pi %' OR r LIKE '%investigator%' OR r LIKE '%left the%'
        OR r LIKE '%staff%' OR r LIKE '%personnel%' THEN 'Investigator / staff'
      WHEN r LIKE '%safety%' OR r LIKE '%adverse%' THEN 'Safety'
      ELSE 'Other / unclear'
    END AS reason_group
  FROM reasons
)
SELECT reason_group,
       COUNT(*) AS trials,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
       SUM(sponsor_class = 'INDUSTRY') AS industry,
       SUM(sponsor_class = 'OTHER') AS academic
FROM grouped
GROUP BY reason_group
ORDER BY trials DESC;
