"""Open the Streamlit app and press the wake-up button if the app is asleep."""
import sys

from playwright.sync_api import sync_playwright

APP_URL = "https://mh-trials-tracker.streamlit.app/"
BUTTON_TEXT = "Yes, get this app back up"


def find_button(page):
    # The sleep page can sit in the main page or inside an iframe.
    for frame in page.frames:
        button = frame.get_by_role("button", name=BUTTON_TEXT)
        if button.count() > 0:
            return button.first
    return None


with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    page.goto(APP_URL, wait_until="domcontentloaded", timeout=90_000)
    page.wait_for_timeout(20_000)

    button = find_button(page)
    if button is None:
        print("App is awake. Nothing to do.")
    else:
        print("App is asleep. Pressing the wake-up button.")
        button.click()
        page.wait_for_timeout(90_000)
        if find_button(page) is not None:
            print("The wake-up button is still showing. The app did not wake.")
            browser.close()
            sys.exit(1)
        print("App woke up.")

    browser.close()
