import os
import sys
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})
    page.goto("http://localhost:8501")
    page.wait_for_timeout(4000)
    
    print("Page Title:", page.title())
    
    # Wait for Streamlit to finish running
    page.wait_for_selector('[data-testid="stAppViewContainer"]')
    page.wait_for_timeout(3000)
    
    all_buttons = page.locator('button').all()
    print(f"Total buttons found: {len(all_buttons)}")
    print("\nClicking '🎯 Product Intelligence'...")
    intel_btn = page.locator('button:has-text("Product Intelligence")').first
    intel_btn.click()
    page.wait_for_timeout(4000)
    
    main_el = page.locator('[data-testid="stMain"]')
    if not main_el.is_visible():
        main_el = page.locator('section.main')
        
    main_text = main_el.inner_text()
    print(f"Main content length: {len(main_text)}")
    print("Main content lines 20 to 60:")
    for line in main_text.splitlines()[20:60]:
        if line.strip():
            print("  >", line.strip())






    browser.close()
