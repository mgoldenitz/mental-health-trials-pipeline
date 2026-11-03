"""
Sensitivity checks for the intervention-name topics (02_machine_learning.ipynb, part H4).

The notebook fits one NMF model: 16 topics, seed 42, assignment threshold 0.02, words and
two-word phrases with min_df=5. This script refits it with other settings and asks whether
the reported trends survive:

  1. Number of topics: 12, 16, 20
  2. Random seed: 42 and four others (16 topics)
  3. Assignment threshold: 0.01, 0.02, 0.05
  4. Preprocessing: single words only; min_df=10

For each run it reports the share of trials with no clear topic and, for each theme, the share
of trials in 2010-12 and 2023-25 assigned to a topic whose ten top words contain the theme's
anchor word. A theme the run did not form as a topic is left blank. Keyword counts on the raw
intervention text are a check that needs no model. Topic stability across seeds is the mean
cosine similarity between each seed-42 topic and its best match in the other run.

Run from the project folder:  python tools/intervention_topic_sensitivity.py
Writes results/ml/H_intervention_topic_sensitivity.csv and H_intervention_topic_stability.csv.
"""

import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "ml"

# Same stop-word lists as the notebook (cell H1)
GENERIC = '''study trial trials effect effects effectiveness efficacy safety randomized randomised controlled pilot
patients patient adults adult treatment treatments evaluation evaluate evaluating clinical versus vs use using based
comparison compare comparing feasibility phase impact people individuals participants subjects healthy volunteers
open label double blind placebo multicenter care intervention interventions program programme disorder disorders
symptoms improve improving reduce reducing group'''.split()
CONDITION_WORDS = '''depression depressive depressed major mdd anxiety social generalized schizophrenia schizoaffective
bipolar ptsd posttraumatic traumatic post stress ocd obsessive compulsive anorexia bulimia nervosa binge eating alcohol
opioid opioids cocaine cannabis substance methamphetamine dependence psychosis psychotic resistant veterans postpartum
children adolescents adolescent youth women older disease related illness severe mood mental health'''.split()
STOP = list(ENGLISH_STOP_WORDS | set(GENERIC) | set(CONDITION_WORDS))

# Theme: (anchor word in a topic's top words, keyword pattern for the model-free count)
THEMES = {
    "Virtual reality": ("virtual", r"virtual reality|\bvr\b"),
    "Apps and mobile": ("app", r"\bapp\b|\bapps\b|mobile|smartphone"),
    "tDCS": ("current", r"direct current|\btdcs\b"),
    "TMS": ("magnetic", r"magnetic stimulation|\btms\b|\brtms\b"),
    "Ketamine": ("ketamine", r"ketamine"),
    "Mindfulness": ("mindfulness", r"mindful"),
    "Music": ("music", r"music"),
    "Exercise": ("exercise", r"exercise|aerobic"),
    "Internet CBT": ("internet", r"internet|online|web"),
    "Sham-controlled": ("sham", r"\bsham\b"),
}
EARLY, LATE = (2010, 2012), (2023, 2025)
SEED = 42


def load():
    read = lambda n: pd.read_csv(ROOT / "data" / "clean" / f"{n}.csv", keep_default_na=False, na_values=[""])
    trials, interventions = read("trials"), read("interventions")
    text = (interventions.assign(intervention_name=lambda d: d.intervention_name.fillna("").astype(str).str.strip())
            .query("intervention_name != ''").groupby("nct_id")["intervention_name"]
            .apply(lambda s: " ".join(sorted(set(s)))).rename("intervention_text"))
    scope = trials[trials["in_scope"] == 1][["nct_id", "start_year"]]
    scope = scope.merge(text, left_on="nct_id", right_index=True, how="left")
    scope["intervention_text"] = scope["intervention_text"].fillna("")
    return scope


def fit(docs, k=16, seed=SEED, ngram=(1, 2), min_df=5):
    vec = TfidfVectorizer(stop_words=STOP, ngram_range=ngram, min_df=min_df, max_df=0.3, sublinear_tf=True)
    X = vec.fit_transform(docs)
    nmf = NMF(n_components=k, init="nndsvda", random_state=seed, max_iter=800)
    W = nmf.fit_transform(X)
    return W, nmf.components_, np.array(vec.get_feature_names_out())


def summarise(scope, W, H, words, threshold, run, setting):
    topic = np.where(W.max(axis=1) >= threshold, W.argmax(axis=1), -1)
    top = [set(" ".join(words[c.argsort()[::-1][:10]]).split()) for c in H]
    years = scope["start_year"].to_numpy()
    early, late = (years >= EARLY[0]) & (years <= EARLY[1]), (years >= LATE[0]) & (years <= LATE[1])
    row = {"run": run, "setting": setting, "no_clear_topic_pct": round((topic == -1).mean() * 100, 1)}
    for theme, (anchor, _) in THEMES.items():
        hits = [i for i, t in enumerate(top) if anchor in t]
        if not hits:
            row[f"{theme} 2010-12"] = row[f"{theme} 2023-25"] = np.nan
            continue
        member = np.isin(topic, hits)
        row[f"{theme} 2010-12"] = round(member[early].mean() * 100, 1)
        row[f"{theme} 2023-25"] = round(member[late].mean() * 100, 1)
    return row


def stability(H_ref, words_ref, H, words):
    """Mean cosine similarity of matched topics (one-to-one), on the shared vocabulary."""
    shared = np.intersect1d(words_ref, words)
    a = H_ref[:, np.searchsorted(words_ref, shared)]
    b = H[:, np.searchsorted(words, shared)]
    sim = cosine_similarity(a, b)
    r, c = linear_sum_assignment(-sim)
    return sim[r, c]


def main():
    scope = load()
    docs = scope["intervention_text"]
    rows, stab = [], []

    W0, H0, w0 = fit(docs)
    rows.append(summarise(scope, W0, H0, w0, 0.02, "notebook", "16 topics, seed 42, threshold 0.02"))

    for k in [12, 20]:
        W, H, w = fit(docs, k=k)
        rows.append(summarise(scope, W, H, w, 0.02, "topics", f"{k} topics"))

    for seed in [0, 1, 2, 3]:
        W, H, w = fit(docs, seed=seed)
        rows.append(summarise(scope, W, H, w, 0.02, "seed", f"seed {seed}"))
        sims = stability(H0, w0, H, w)
        stab.append({"seed": seed, "mean_similarity": round(sims.mean(), 3),
                     "topics_above_0.8": int((sims > 0.8).sum()), "lowest": round(sims.min(), 3)})

    for t in [0.01, 0.05]:
        rows.append(summarise(scope, W0, H0, w0, t, "threshold", f"threshold {t}"))

    W, H, w = fit(docs, ngram=(1, 1))
    rows.append(summarise(scope, W, H, w, 0.02, "preprocessing", "single words only"))
    W, H, w = fit(docs, min_df=10)
    rows.append(summarise(scope, W, H, w, 0.02, "preprocessing", "min_df 10"))

    # Model-free check: share of trials whose intervention text matches the keyword
    years = scope["start_year"]
    kw = {"run": "keyword", "setting": "keyword match, no model", "no_clear_topic_pct": np.nan}
    low = docs.str.lower()
    for theme, (_, pattern) in THEMES.items():
        hit = low.str.contains(pattern, regex=True)
        kw[f"{theme} 2010-12"] = round(hit[years.between(*EARLY)].mean() * 100, 1)
        kw[f"{theme} 2023-25"] = round(hit[years.between(*LATE)].mean() * 100, 1)
    rows.append(kw)

    out = pd.DataFrame(rows)
    out.to_csv(OUT / "H_intervention_topic_sensitivity.csv", index=False)
    pd.DataFrame(stab).to_csv(OUT / "H_intervention_topic_stability.csv", index=False)
    pd.set_option("display.width", 250)
    print(out.T.to_string(header=False))
    print(pd.DataFrame(stab).to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
