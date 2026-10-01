import sys
import time
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})

    print("Navigating to http://localhost:8501 ...")
    t0 = time.time()
    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stAppViewContainer"]')
    
    print("Waiting for Streamlit to finish running (waiting for skeletons to detach)...")
    # Wait until skeletons are gone or timeout
    try:
        page.wait_for_selector('[data-testid="stSkeleton"]', state='detached', timeout=60000)
        print(f"All skeletons detached after {round(time.time() - t0, 1)}s!")
    except Exception as e:
        print(f"Warning/Timeout waiting for skeletons: {e}")
        
    page.wait_for_timeout(2000)
    
    # Now check buttons in Block 1
    blocks = page.evaluate("""() => {
        const hblocks = Array.from(document.querySelectorAll('div[data-testid="stHorizontalBlock"]'));
        const b1Btns = hblocks[1] ? Array.from(hblocks[1].querySelectorAll('button')).map(b => b.textContent.trim()) : [];
        const b2Btns = hblocks[2] ? Array.from(hblocks[2].querySelectorAll('button')).map(b => b.textContent.trim()) : [];
        return { b1Btns, b2Btns };
    }""")
    
    print("Row 1 Navigation Buttons:", blocks['b1Btns'])
    print("Row 2 Navigation Buttons:", blocks['b2Btns'])
    
    # Now let's click '🎯 Product Intelligence'!
    intel_btn = page.locator('button:has-text("Product Intelligence")').first
    print("\nProduct Intelligence button is_visible:", intel_btn.is_visible())
    if intel_btn.is_visible():
        print("Clicking '🎯 Product Intelligence'...")
        intel_btn.click()
        
        # Wait for Streamlit to finish rerun
        print("Waiting for rerun to complete...")
        try:
            page.wait_for_selector('[data-testid="stSkeleton"]', state='detached', timeout=45000)
        except Exception:
            pass
        page.wait_for_timeout(3000)
        
        main_text = page.locator('[data-testid="stMain"]').inner_text()
        has_intel = "Product Opportunity Intelligence Engine" in main_text
        print(f"Switched to Product Intelligence? {has_intel}")
        
        # Check subtabs!
        subtabs = page.locator('[role="tab"]').all()
        print(f"Subtabs rendered ({len(subtabs)}):")
        for s in subtabs:
            print("  Subtab:", repr(s.inner_text().strip()))

    browser.close()
