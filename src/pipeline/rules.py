"""Condition grouping and psychedelic / ketamine flags, copied from notebook cells C2 and C3."""

import re

EXCLUDE = (r"respiratory depression|cns depression"
           r"|(pre|post|peri)[- ]?operative anxiety|anxiety,? (pre|post|peri)[- ]?operative"
           r"|presurgical|pre-surgical|surgical anxiety|surgery anxiety"
           r"|dental anxiety|dental fear|procedural anxiety|kinesiophobia|traumatic brain injury")

GROUPS = {
    # Bipolar is checked before Depression so "Bipolar Depression" counts as bipolar disorder
    "Bipolar disorder": r"bi-?polar|\bmania\b|manic",
    "Depression": r"depress|dysthym|\bmdd\b|anhedonia",
    "Anxiety": r"anxi|panic|phobi|\bgad\b|agoraphobi",
    "OCD": r"obsessive|\bocd\b",
    "PTSD": (r"ptsd|post\s*-?\s*traumatic|acute stress disorder|stress disorders?,? acute"
             r"|stress disorders?,? (post[- ]?)?traumatic|traumatic stress disorder"),
    "Schizophrenia & psychosis": r"schizo|psychosis|psychoses|psychotic",
    "Substance use": (r"substance|alcohol use|alcohol abuse|alcohol dependence|alcoholism"
                      r"|hazardous alcohol|heavy drinking|binge drinking"
                      r"|opioid|opiate|cocaine|methamphetamine|stimulant use|cannabis use"
                      r"|addict|use disorder|dependence"
                      r"|alcohol[- ]abuse|alcohol[- ]related disorder|alcohol;? (use|harmful)|alcohol withdrawal"
                      r"|(drug|cannabis|marijuana|amphetamine|benzodiazepine|inhalant)s? (use|abuse|misuse)"),
    "Eating disorders": (r"anorexia nervosa|bulimi|binge.?eating|eating,? binge|eating disorder|\barfid\b"
                         r"|avoidant\W*restrictive|disordered eating|feeding disorder,? (of )?infancy"),
}

# Added in v2 (November 2026). They are matched after GROUPS and do not change it, so
# the published groups and counts stay as they were. A condition can match more than one
# of these, and can match one of these as well as one of GROUPS ("Anxiety in Autism").
NEW_GROUPS = {
    # "attention deficits" alone is a cognitive symptom (in schizophrenia, for example)
    "ADHD": r"attention[- ]?deficit\W*(and\W*)?(hyperactiv|disorder)|\badhd\b|hyperkinetic disorder",
    "Autism spectrum": r"autis|asperger|pervasive developmental",
    "Personality disorders": (r"personality disorder|borderline personality|antisocial personality"
                              r"|schizotypal personality|psychopathy\b"),
    "Gambling & gaming disorders": (r"gambl|gaming disorder|internet gaming|gaming addiction"
                          r"|video game addiction|internet addiction|problematic internet use"),
}

# A flag, not a group: DSM-5-TR lists suicidal behaviour and self-harm as conditions for
# clinical attention, not as disorders. Matched on the condition names and the title.
SUICIDE = r"suicid|self[- ]?harm|self[- ]?injur|\bnssi\b"

PSYCHEDELIC = (
    # substances
    r"psilocybin|psilocin|mdma|midomafetamine|\blsd\b|lysergic"
    r"|\bdmt\b|dimethyltryptamine|5-meo|ayahuasca|ibogaine|noribogaine"
    r"|mescaline|salvinorin|psychedelic"
    # company drug codes
    r"|comp ?360"        # Compass Pathways, psilocybin
    r"|mm-?120"          # MindMed, LSD
    r"|cyb00[34]"        # Cybin, deuterated psilocybin analogue / DMT
    r"|gh00[12]"         # GH Research, 5-MeO-DMT
    r"|bpl-?003"         # Beckley Psytech, 5-MeO-DMT nasal spray
    r"|spl0?26"          # Small Pharma, DMT
    r"|re-?104"          # Reunion Neuroscience, psilocybin-like prodrug
    r"|bmnd0\d"          # Biomind Labs, 5-MeO-DMT
)
KETAMINE = r"ketamine|spravato"   # also matches esketamine and arketamine


def group_of(text):
    t = text.lower() if isinstance(text, str) else ""
    if re.search(EXCLUDE, t):
        return "Other"
    for name, pattern in GROUPS.items():
        if re.search(pattern, t):
            return name
    return "Other"


def new_groups(text):
    """Every NEW_GROUPS name the condition matches (empty if none, or if EXCLUDE matches)."""
    t = text.lower() if isinstance(text, str) else ""
    if re.search(EXCLUDE, t):
        return []
    return [name for name, pattern in NEW_GROUPS.items() if re.search(pattern, t)]


def suicide_flag(*texts):
    return any(isinstance(t, str) and re.search(SUICIDE, t.lower()) for t in texts)


def drug_class(name):
    n = name.lower() if isinstance(name, str) else ""
    if n.startswith("placebo") or "matched placebo" in n:
        return None
    if re.search(PSYCHEDELIC, n):
        return "Psychedelic / MDMA"
    if re.search(KETAMINE, n):
        return "Ketamine / esketamine"
    return None
