"""
Classify the free-text "why stopped" reasons with Amazon Bedrock and compare the
result with the keyword grouping in sql/05b_why_stopped_grouped.sql.

  python tools/classify_why_stopped.py                 # estimate only, no AWS calls
  python tools/classify_why_stopped.py --run           # classify and write results

Only trials that are TERMINATED, WITHDRAWN or SUSPENDED and have a reason are
sent. Labels are cached in data/llm/why_stopped_labels.csv, keyed by NCT ID and
reason text, so a later run sends only new trials or reasons that changed.
Identical reason texts are sent once.

To label a newer weekly snapshot, download its trials table first, e.g.
  aws s3 cp s3://BUCKET/snapshots/2026-11-02/trials.csv out/trials.csv --profile personal
and pass --trials out/trials.csv.

Needs boto3 (in requirements.txt) and an AWS profile allowed to call
bedrock:InvokeModel on the chosen model.
"""

import argparse
import csv
import re
import sys
import time
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TRIALS = ROOT / "data" / "powerbi" / "trials.csv"
CACHE = ROOT / "data" / "llm" / "why_stopped_labels.csv"
OUT_DIR = ROOT / "results" / "ml"

# Nova Micro through the US cross-Region inference profile (needed in us-east-2).
DEFAULT_MODEL = "us.amazon.nova-micro-v1:0"
# USD per 1,000,000 tokens, Nova Micro on-demand. Check the Bedrock pricing page
# and pass --price-in / --price-out if they have changed.
PRICE_IN = 0.035
PRICE_OUT = 0.14

STOPPED = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
BATCH = 40

# Code sent to and returned by the model -> label used in the results.
CATEGORIES = {
    "RECRUITMENT": "Recruitment",
    "FUNDING": "Funding",
    "SPONSOR": "Sponsor / business decision",
    "EFFICACY": "Efficacy / futility",
    "SAFETY": "Safety",
    "COVID": "COVID-19",
    "STAFF": "Investigator / staff",
    "REGULATORY": "Regulatory / ethics",
    "LOGISTICS": "Logistics / drug supply",
    "DESIGN": "Study design change",
    "OTHER": "Other / unclear",
}

SYSTEM_PROMPT = """You label why a clinical trial stopped early. Each input line is
"ID: reason", where the reason is free text a sponsor wrote on ClinicalTrials.gov.
Pick the ONE category that names the main cause. If a reason gives several causes,
pick the one that ended the study.

RECRUITMENT  slow, low or no enrolment; participants hard to find or retain; eligibility problems
FUNDING      funding or a grant ended, was not obtained, or the budget ran out
SPONSOR      sponsor, company or portfolio decision; business or strategic reasons; program cancelled;
             sponsor or company went out of business
EFFICACY     lack of efficacy, futility, or an interim analysis showing the study would not meet its goal
             (a report of good results is not EFFICACY; label the reason the study stopped)
SAFETY       safety concerns or adverse events
COVID        the COVID-19 pandemic (use this even when the pandemic caused recruitment or site problems)
STAFF        principal investigator left, retired or died; staff or personnel shortages
REGULATORY   ethics board, IRB, FDA or other regulator decisions, approvals, holds or compliance
LOGISTICS    drug or device supply, site closure, technical, contract or operational problems
DESIGN       protocol changed, study replaced by a new or redesigned study, or design flaws
OTHER        anything else, or a reason too vague to tell (e.g. "terminated", "PI decision" with no cause)

Answer with one line per input, in the same order, formatted exactly as
ID|CATEGORY
Write nothing else."""

LINE = re.compile(r"^\s*(\d+)\s*[|:]\s*([A-Z]+)")


def keyword_group(reason):
    """The CASE expression from sql/05b_why_stopped_grouped.sql, first match wins."""
    r = reason.lower()

    def has(*words):
        return any(w in r for w in words)

    if has("covid", "pandemic", "coronavirus"):
        return "COVID-19"
    if has("efficacy", "futility", "interim analys"):
        return "Efficacy / futility"
    if has("sponsor decision", "business", "strategic", "portfolio", "company decision", "program"):
        return "Sponsor / business decision"
    if has("fund", "budget", "financ"):
        return "Funding"
    if has("recruit", "enrol", "accrual", "participant", "subject", "patient"):
        return "Recruitment"
    if has("pi ", "investigator", "left the", "staff", "personnel"):
        return "Investigator / staff"
    if has("safety", "adverse"):
        return "Safety"
    return "Other / unclear"


def load_trials(path):
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and "in_scope" in rows[0]:
        rows = [r for r in rows if r["in_scope"] == "1"]
    return [r for r in rows
            if r["overall_status"] in STOPPED and (r.get("why_stopped") or "").strip()]


def load_cache():
    if not CACHE.exists():
        return {}
    with open(CACHE, encoding="utf-8", newline="") as f:
        return {(r["nct_id"], r["why_stopped"]): r for r in csv.DictReader(f)}


def save_cache(cache):
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cols = ["nct_id", "why_stopped", "llm_category", "model", "labelled_on"]
    with open(CACHE, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for key in sorted(cache):
            w.writerow({c: cache[key][c] for c in cols})


def norm(text):
    return " ".join(text.split())


def user_prompt(texts):
    return "\n".join(f"{i + 1}: {t}" for i, t in enumerate(texts))


def estimate_tokens(texts):
    """Rough count at about 4 characters per token, plus the system prompt per call."""
    calls = -(-len(texts) // BATCH)
    tin = calls * len(SYSTEM_PROMPT) / 4 + sum(len(t) + 6 for t in texts) / 4
    tout = len(texts) * 6
    return calls, int(tin), int(tout)


def parse(reply, n):
    labels = {}
    for line in reply.splitlines():
        m = LINE.match(line)
        if m and m.group(2) in CATEGORIES and 1 <= int(m.group(1)) <= n:
            labels[int(m.group(1)) - 1] = m.group(2)
    return labels


class Classifier:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self.tokens_in = 0
        self.tokens_out = 0

    def call(self, texts):
        resp = self.client.converse(
            modelId=self.model,
            system=[{"text": SYSTEM_PROMPT}],
            messages=[{"role": "user", "content": [{"text": user_prompt(texts)}]}],
            inferenceConfig={"maxTokens": 20 * len(texts) + 50, "temperature": 0},
        )
        self.tokens_in += resp["usage"]["inputTokens"]
        self.tokens_out += resp["usage"]["outputTokens"]
        return parse(resp["output"]["message"]["content"][0]["text"], len(texts))

    def label(self, texts):
        """Return {text: code}. Items the model skips are retried one at a time."""
        out = {}
        for start in range(0, len(texts), BATCH):
            chunk = texts[start:start + BATCH]
            got = self.call(chunk)
            for i, t in enumerate(chunk):
                if i in got:
                    out[t] = got[i]
                else:
                    single = self.call([t])
                    if 0 in single:
                        out[t] = single[0]
            print(f"  {min(start + BATCH, len(texts)):,} of {len(texts):,} reasons labelled")
        return out


def write_results(trials, cache):
    rows = []
    for t in trials:
        hit = cache.get((t["nct_id"], norm(t["why_stopped"])))
        if hit:
            rows.append((t, keyword_group(t["why_stopped"]), hit["llm_category"]))
    if not rows:
        return
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    n = len(rows)
    by_llm = Counter(llm for _, _, llm in rows)
    path = OUT_DIR / "I_why_stopped_llm_groups.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["reason_group", "trials", "pct", "industry", "academic", "keyword_trials"])
        kw = Counter(k for _, k, _ in rows)
        for group, count in by_llm.most_common():
            w.writerow([group, count, round(100 * count / n, 1),
                        sum(1 for t, _, l in rows if l == group and t["sponsor_class"] == "INDUSTRY"),
                        sum(1 for t, _, l in rows if l == group and t["sponsor_class"] == "OTHER"),
                        kw.get(group, 0)])
    print(f"wrote {path.relative_to(ROOT)}")

    pairs = Counter((k, l) for _, k, l in rows)
    path = OUT_DIR / "I_why_stopped_llm_vs_keyword.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["keyword_group", "llm_category", "trials"])
        for (k, l), c in sorted(pairs.items(), key=lambda x: (-x[1], x[0])):
            w.writerow([k, l, c])
    print(f"wrote {path.relative_to(ROOT)}")

    path = OUT_DIR / "I_why_stopped_disagreements.csv"
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nct_id", "why_stopped", "keyword_group", "llm_category"])
        for t, k, l in sorted(rows, key=lambda x: (x[1], x[2], x[0]["nct_id"])):
            if k != l:
                w.writerow([t["nct_id"], norm(t["why_stopped"]), k, l])
    print(f"wrote {path.relative_to(ROOT)}")

    agree = sum(1 for _, k, l in rows if k == l)
    other_kw = sum(1 for _, k, _ in rows if k == "Other / unclear")
    other_llm = by_llm.get("Other / unclear", 0)
    print(f"\n{n:,} trials labelled. Keyword and model agree on {agree:,} ({100 * agree / n:.1f}%).")
    print(f"'Other / unclear': keyword rules {other_kw:,}, model {other_llm:,}.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--trials", default=str(DEFAULT_TRIALS), help="trials table (CSV)")
    ap.add_argument("--run", action="store_true", help="call Bedrock; without it only the estimate is printed")
    ap.add_argument("--profile", default="personal")
    ap.add_argument("--region", default="us-east-2")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--price-in", type=float, default=PRICE_IN, help="USD per 1M input tokens")
    ap.add_argument("--price-out", type=float, default=PRICE_OUT, help="USD per 1M output tokens")
    ap.add_argument("--limit", type=int, help="send at most this many reasons (for a trial run)")
    args = ap.parse_args()

    trials = load_trials(args.trials)
    cache = load_cache()
    todo = [t for t in trials if (t["nct_id"], norm(t["why_stopped"])) not in cache]
    texts = sorted({norm(t["why_stopped"]) for t in todo})
    if args.limit:
        texts = texts[:args.limit]

    calls, tin, tout = estimate_tokens(texts)
    cost = tin / 1e6 * args.price_in + tout / 1e6 * args.price_out
    print(f"{len(trials):,} stopped trials with a reason; {len(trials) - len(todo):,} already labelled.")
    print(f"To send: {len(texts):,} distinct reasons in {calls} calls, "
          f"about {tin:,} input and {tout:,} output tokens, about USD {cost:.4f} with {args.model}.")

    if args.run and texts:
        import boto3
        client = boto3.Session(profile_name=args.profile, region_name=args.region).client("bedrock-runtime")
        clf = Classifier(client, args.model)
        t0 = time.time()
        labels = clf.label(texts)
        today = date.today().isoformat()
        for t in todo:
            code = labels.get(norm(t["why_stopped"]))
            if code:
                cache[(t["nct_id"], norm(t["why_stopped"]))] = {
                    "nct_id": t["nct_id"], "why_stopped": norm(t["why_stopped"]),
                    "llm_category": CATEGORIES[code], "model": args.model, "labelled_on": today}
        save_cache(cache)
        actual = clf.tokens_in / 1e6 * args.price_in + clf.tokens_out / 1e6 * args.price_out
        print(f"Done in {time.time() - t0:.0f} s: {clf.tokens_in:,} input and {clf.tokens_out:,} "
              f"output tokens, USD {actual:.4f}. {len(texts) - len(labels)} reasons left unlabelled.")
    elif not args.run:
        print("Estimate only. Add --run to call Bedrock.")

    write_results(trials, cache)


if __name__ == "__main__":
    sys.exit(main())
