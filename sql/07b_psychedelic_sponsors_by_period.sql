SELECT i.psychedelic_class,
       CASE WHEN t.start_year >= 2021 THEN '2021-2025' ELSE '2010-2020' END AS period,
       t.sponsor_class,
       COUNT(DISTINCT t.nct_id) AS trials
FROM trials t JOIN interventions i ON t.nct_id = i.nct_id
WHERE i.psychedelic_class IS NOT NULL AND t.in_scope = 1
GROUP BY 1, 2, 3
ORDER BY 1, 2, trials DESC;
