"""Download studies from the ClinicalTrials.gov API (version 2), one page at a time (notebook cell B2)."""

import json
import time
import urllib.parse
import urllib.request

BASE = "https://clinicaltrials.gov/api/v2/studies"

QUERY_COND = ('depression OR anxiety OR PTSD OR "bipolar disorder" '
              'OR schizophrenia OR psychosis OR "substance use disorder" '
              'OR "obsessive-compulsive disorder" OR "eating disorder" '
              'OR "anorexia nervosa" OR "bulimia nervosa" OR "binge eating disorder"')


def search_params(start="2010-01-01", end="2025-12-31"):
    return {
        "query.cond": QUERY_COND,
        "filter.advanced": ("AREA[StudyType]INTERVENTIONAL AND "
                            f"AREA[StartDate]RANGE[{start},{end}]"),
        "pageSize": 1000,
        "countTotal": "true",
        "format": "json",
    }


def get_json(params, timeout=120, tries=4):
    url = BASE + "?" + urllib.parse.urlencode(params)
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=timeout) as r:
                return json.load(r)
        except OSError:
            if attempt == tries - 1:
                raise
            time.sleep(2 ** (attempt + 1))   # 2, 4, 8 seconds


def pages(start="2010-01-01", end="2025-12-31"):
    """Yield one API page (a dict with "studies", and "totalCount" on the first page) at a time."""
    params = search_params(start, end)
    while True:
        page = get_json(params)
        yield page
        token = page.get("nextPageToken")
        if not token:
            return
        params["pageToken"] = token
        time.sleep(0.3)   # be polite to the server
