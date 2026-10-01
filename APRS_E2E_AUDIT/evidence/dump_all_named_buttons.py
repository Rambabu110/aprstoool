import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})

    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stAppViewContainer"]')
    page.wait_for_timeout(6000)
    
    all_btns = page.locator('button').all()
    print(f"Total buttons on page: {len(all_btns)}")
    
    named_btns = []
    for i, b in enumerate(all_btns):
        txt = b.text_content().strip().replace('\n', ' ')
        if txt:
            named_btns.append((i, txt, b.is_visible()))
            
    print(f"Buttons with text_content: {len(named_btns)}")
    for idx, txt, vis in named_btns[:40]:
        print(f"  #{idx} [vis={vis}]: '{txt}'")


    browser.close()
