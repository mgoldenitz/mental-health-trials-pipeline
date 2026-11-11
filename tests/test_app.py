"""Smoke test for the Streamlit app: every page runs without an error and the headline numbers
match the published analysis. Runs without AWS secrets, so the weekly pages show their
"not connected" notes and Find trials uses the published snapshot."""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).resolve().parents[1] / "app.py")
PAGES = ["views/overview.py", "views/find_trials.py", "views/psychedelics.py", "views/canada.py",
         "views/about.py", "views/latest_refresh.py", "views/new_groups.py", "views/health_canada.py"]


@pytest.fixture
def app():
    at = AppTest.from_file(APP, default_timeout=120)
    at.run()
    assert not at.exception
    return at


def test_published_headline_numbers(app):
    metrics = {m.label: m.value for m in app.metric}
    assert metrics["Trials"] == "14,724"
    assert metrics["Recruiting now"] == "1,726"
    assert metrics["Psychedelic & Ketamine"] == "479"
    assert metrics["In Canada"] == "1,020"
    assert metrics["Posted results"] == "27%"


@pytest.mark.parametrize("page", PAGES)
def test_page_runs(app, page):
    app.switch_page(page).run()
    assert not app.exception, [e.value for e in app.exception]


def test_filter_and_clear(app):
    app.sidebar.multiselect(key="condition").select("Depression").run()
    assert app.metric[0].value == "6,817"
    for key, value in [("country", ["Canada"]), ("phase", ["Phase 4"]), ("condition", ["Eating disorders"])]:
        app.sidebar.multiselect(key=key).set_value(value).run()
    app.sidebar.toggle(key="psychedelic").set_value(True).run()
    assert any("No published trials match" in w.value for w in app.warning)
    # Pages still draw when nothing matches
    app.switch_page("views/about.py").run()
    assert not app.exception
    app.switch_page("views/overview.py").run()
    app.button(key="clear_main").click().run()
    assert app.metric[0].value == "14,724"


def test_search(app):
    app.switch_page("views/find_trials.py").run()
    app.text_input(key="q").input("psilocybin").run()
    assert not app.exception
    assert any("trials" in c.value and "Published snapshot" in c.value for c in app.caption)
