# Checks on the intervention-name topics

Part H4 of `02_machine_learning.ipynb` fits one NMF model to intervention names: 16 topics, seed 42, a trial assigned to its strongest topic when that weight is at least 0.02. `tools/intervention_topic_sensitivity.py` refits it with other settings to see which trends depend on those choices. It uses the same 14,724 published trials (1,701 started in 2010 to 2012, 4,245 in 2023 to 2025) and changes nothing in the notebook, the app or the published results.

The runs: 12 and 20 topics; seeds 0 to 3; thresholds 0.01 and 0.05; single words only; and a minimum of 10 trials per word instead of 5. For each run and theme, a trial counts toward the theme when its assigned topic has the theme's anchor word among its ten top words. A keyword count on the raw intervention names, with no model, is the independent check. Output is in `results/ml/H_intervention_topic_sensitivity.csv` and `results/ml/H_intervention_topic_stability.csv`.

## Results

The topics are stable across seeds. Seeds 1, 2 and 3 reproduce all 16 topics exactly (cosine similarity 1.0). Seed 0 reproduces 15 and replaces one, which changes the "app" and "TMS" shares but not their direction.

Coverage depends on the threshold. 52% of trials have no clear topic at 0.02, 46% at 0.01 and 59% at 0.05, and 49% to 58% across 12 to 20 topics. The share of trials in a topic is a share of all trials, so a theme that sits mostly in unassigned trials is undercounted.

These trends held in every run and agree with the keyword count:

- Virtual reality: 0.2% to 4.4% in every run (4.2% to 4.6% across thresholds). Keyword count 0.3% to 5.1%.
- Music: 0.6% to 2.0%-2.2% in every run. Keyword count 0.6% to 2.3%.
- Sham-controlled stimulation: 2.5%-4.8% to 5.8%-8.3%. Keyword count for "sham" 1.9% to 6.2%. The notebook labels this topic "sham, tdcs, active", but its top words also include rTMS and iTBS, so it tracks sham-controlled brain stimulation trials in general, not tDCS alone.
- Ketamine: about flat (1.7% to 1.4% in the model, 1.6% to 1.7% by keyword). Ketamine trials grew in number, but not as a share of all trials.
- Exercise: a small rise in every run (about 1.8% to 2.3%), matched by the keyword count (2.1% to 2.7%).

These need care:

- "App, education, mobile" (reported +3.3 points) mixes mobile apps with education and usual-care wording. Its size swings from 2.1% to 10.5% in 2023 to 2025 depending on the settings. The keyword count for apps and mobile rose from 0.1% to 2.7%, so app trials did grow, but the topic overstates the size.
- "CBT, internet, tf" fell in the notebook (2.7% to 1.4%), but the keyword count for internet, online or web interventions rose (2.2% to 2.7%). The topic's fall reflects CBT wording, so it should not be read as internet-delivered treatment declining.
- "Mindfulness, reduction, psychoeducation" grows in most runs, but its level is about twice the keyword count for mindfulness (1.7% to 3.0%), because it also absorbs psychoeducation and cognitive therapy.
- tDCS on its own (the "current, direct, stimulation" topic) rises from 0.7% to 1.3%, close to the keyword count (1.0% to 1.7%), except in the single-words run, where it merges with other stimulation terms.

## What this means for reporting

The virtual reality, music and sham-controlled stimulation increases and the flat ketamine share can be described as robust to these settings, with the topics still labelled exploratory. The app, internet CBT and mindfulness topics should not be quoted as sizes, and the internet CBT decline should not be quoted at all. The topic labels are still the top words chosen by the model; nobody has reviewed them against a set of hand-coded trials.
