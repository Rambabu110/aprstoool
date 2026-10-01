import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})

    page.goto("http://localhost:8501")
    # Wait until Streamlit is 100% idle and not running
    print("Waiting for page load...")
    page.wait_for_selector('[data-testid="stAppViewContainer"]')
    
    # Wait for the Streamlit status runner indicator to disappear
    # Streamlit shows [data-testid="stStatusWidget"] when running!
    page.wait_for_timeout(5000)
    
    # Let's see all buttons with class st-key-nav_*
    nav_keys = [
        "nav_intelligence", "nav_opps", "nav_price_compare", "nav_trending",
        "nav_predictions", "nav_launchpad", "nav_meeting", "nav_keepa",
        "nav_supplier", "nav_econ", "nav_db_explorer", "nav_archive"
    ]
    for k in nav_keys:
        loc = page.locator(f'.st-key-{k} button')
        if loc.count() > 0:
            btn = loc.first
            print(f"Key {k}: count={loc.count()}, visible={btn.is_visible()}, box={btn.bounding_box()}, text={repr(btn.inner_text().strip())}")
        else:
            print(f"Key {k}: NOT FOUND in DOM")

    browser.close()
