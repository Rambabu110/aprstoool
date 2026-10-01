import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1050})
    page.goto("http://localhost:8501")
    page.wait_for_timeout(4000)
    
    btn = page.get_by_role("button", name="🎯 Product Intelligence")
    print("Found button visible:", btn.is_visible())
    btn.click()
    page.wait_for_timeout(4000)
    
    tabs = page.locator('[role="tab"]')
    print(f"Tabs count after click: {tabs.count()}")
    for i in range(tabs.count()):
        print(f"Tab {i}: {tabs.nth(i).inner_text()}")
        
    browser.close()
