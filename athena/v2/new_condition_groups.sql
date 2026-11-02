-- v2 condition groups (added November 2026) in the newest weekly refresh
-- (database mental_health_trials). Not part of the published analysis, so
-- tools/run_athena.py does not run it; paste it into the Athena query editor.
SELECT c.condition_group,
       COUNT(DISTINCT t.nct_id) AS trials,
       COUNT(DISTINCT CASE WHEN t.scope = 'extended' THEN t.nct_id END) AS extended_scope,
       COUNT(DISTINCT CASE WHEN t.suicide_flag THEN t.nct_id END) AS suicide_flag,
       COUNT(DISTINCT CASE WHEN t.sponsor_type = 'Companies' THEN t.nct_id END) AS industry
FROM trials t
JOIN conditions c ON t.nct_id = c.nct_id
WHERE t.start_year BETWEEN 2010 AND 2025
  AND c.condition_group IN ('ADHD', 'Autism spectrum', 'Personality disorders', 'Gambling & gaming disorders')
GROUP BY c.condition_group
ORDER BY trials DESC;
