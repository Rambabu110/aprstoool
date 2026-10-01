import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    page = browser.new_page(viewport={"width": 1600, "height": 1000})

    page.goto("http://localhost:8501")
    page.wait_for_selector('[data-testid="stAppViewContainer"]')
    page.wait_for_timeout(4000)
    
    # Run in browser via JS
    result = page.evaluate("""() => {
        const headings = Array.from(document.querySelectorAll('h1, h2, h3, h4, [data-testid="stHeading"]')).map(h => ({
            tag: h.tagName,
            text: h.textContent.trim()
        }));
        return {
            title: document.title,
            headings: headings,
            bodyStart: document.body.innerText.slice(0, 1000)
        };
    }""")
    
    # Print innerHTML of Block 1 and Block 2
    htmls = page.evaluate("""() => {
        const hblocks = Array.from(document.querySelectorAll('div[data-testid="stHorizontalBlock"]'));
        return {
            b1: hblocks[1]?.innerHTML || 'none',
            b2: hblocks[2]?.innerHTML || 'none'
        };
    }""")
    print("Block 1 HTML snippet:")
    print(htmls['b1'][:500])
    print("\nBlock 2 HTML snippet:")
    print(htmls['b2'][:500])

    
    print(f"Total stHorizontalBlock found: {len(blocks)}")
    for hb in blocks[:10]:
        print(f"  Block #{hb['index']} [rect={hb['rect']}]: {hb['btnCount']} buttons -> {hb['btns']}")


    
    # Inspect matching elements
    matches = page.evaluate("""() => {
        const allElements = Array.from(document.querySelectorAll('*'));
        const found = [];
        allElements.forEach(el => {
            if (el.children.length === 0 && el.textContent.includes('Product')) {
                const rect = el.getBoundingClientRect();
                found.push({
                    tagName: el.tagName,
                    text: el.textContent.trim(),
                    parentTag: el.parentElement?.tagName,
                    btnParent: el.closest('button')?.tagName || 'none',
                    rect: { x: Math.round(rect.x), y: Math.round(rect.y), w: Math.round(rect.width), h: Math.round(rect.height) }
                });
            }
        });
        return found;
    }""")
    
    print(f"Elements matching 'Product' ({len(matches)}):")
    for m in matches[:15]:
        print(f"  {m['tagName']} inside {m['parentTag']} (btn: {m['btnParent']}) | text='{m['text']}' | rect={m['rect']}")





    browser.close()
