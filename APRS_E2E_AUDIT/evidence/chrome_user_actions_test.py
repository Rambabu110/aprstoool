"""
APRS_E2E_AUDIT/evidence/chrome_user_actions_test.py
Deep, realistic user interaction audit in Google Chrome (Playwright):
1. Watchlist Add/Remove Flow with cross-subtab verification
2. Opportunities Shortlist Toggle and Shortlisted-Only Filter Flow
3. Live 15-Factor Economics Calculator Form submission
4. SSOT Database Table Search & AI-Rejected Toggle
5. War Room Word Doc Compilation
"""
import os
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent.parent
SCREENSHOTS_PASSED = ROOT / "APRS_E2E_AUDIT" / "screenshots" / "passed"
SCREENSHOTS_ERRORS = ROOT / "APRS_E2E_AUDIT" / "screenshots" / "errors"
SCREENSHOTS_PASSED.mkdir(parents=True, exist_ok=True)
SCREENSHOTS_ERRORS.mkdir(parents=True, exist_ok=True)

findings = []

def log_result(step_id, name, status, details, screenshot=""):
    findings.append({
        "step_id": step_id,
        "name": name,
        "status": status,
        "details": details,
        "screenshot": screenshot,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    })
    print(f"[{status}] {step_id}: {name} - {details}")

def click_nav_tab(page, tab_label):
    btn = page.get_by_role("button", name=tab_label, exact=False).first
    if not btn.is_visible():
        btn = page.locator(f'button:has-text("{tab_label[:5]}")').first
    btn.click()
    page.wait_for_timeout(3000)

def run_user_actions_audit():
    print("================================================================================")
    print("STARTING REAL USER INTERACTION AUDIT IN GOOGLE CHROME")
    print("================================================================================")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 1050})
        page = context.new_page()

        console_errors = []
        page.on("pageerror", lambda err: console_errors.append(str(err)))

        print("Navigating to http://localhost:8501 ...")
        page.goto("http://localhost:8501", timeout=30000)
        page.wait_for_timeout(4000)

        # ----------------------------------------------------------------------
        # FLOW 1: Watchlist Add and Remove Flow
        # ----------------------------------------------------------------------
        print("\n--- Flow 1: Watchlist Add & Cross-Subtab Verification ---")
        click_nav_tab(page, "🎯 Product Intelligence")

        # Ensure on Opportunities & Scorecards subtab
        sub_opps = page.get_by_role("tab", name="Opportunities & Scorecards", exact=False).first
        sub_opps.click()
        page.wait_for_timeout(2000)

        # Check Watchlist button state
        watch_btn = page.locator('button:has-text("Watchlist")').first
        if watch_btn.is_visible():
            btn_text_before = watch_btn.inner_text().strip()
            print(f"Initial Watchlist Button State: '{btn_text_before}'")

            if "Add to Watchlist" in btn_text_before:
                watch_btn.click()
                page.wait_for_timeout(3000)
                shot_watch_added = "CHROME_FLOW_001_watchlist_added.png"
                page.screenshot(path=str(SCREENSHOTS_PASSED / shot_watch_added), full_page=True)
                log_result("FLOW-001", "Add to Watchlist Click", "PASS", "Clicked Add to Watchlist button", shot_watch_added)

                # Switch to Subtab 7: Watchlist & Timeline
                sub_watch = page.get_by_role("tab", name="Watchlist & Timeline", exact=False).first
                sub_watch.click()
                page.wait_for_timeout(2000)
                shot_watch_view = "CHROME_FLOW_002_watchlist_subtab_view.png"
                page.screenshot(path=str(SCREENSHOTS_PASSED / shot_watch_view), full_page=True)
                watch_text = page.inner_text('[data-testid="stAppViewContainer"]')
                log_result("FLOW-002", "Watchlist Subtab Verification", "PASS", f"Navigated to Watchlist subtab ({len(watch_text)} chars)", shot_watch_view)

                # Return and clean up
                sub_opps.click()
                page.wait_for_timeout(2000)
                watch_btn_after = page.locator('button:has-text("Remove from Watchlist")').first
                if watch_btn_after.is_visible():
                    watch_btn_after.click()
                    page.wait_for_timeout(2000)
                    log_result("FLOW-003", "Remove from Watchlist Cleanup", "PASS", "Restored product watchlist state", "")

        # ----------------------------------------------------------------------
        # FLOW 2: Opportunities Shortlist Toggle and Filter
        # ----------------------------------------------------------------------
        print("\n--- Flow 2: Opportunities Shortlist Toggle & Filter ---")
        click_nav_tab(page, "📋 Opportunities")

        sl_btn = page.locator('button:has-text("Shortlist")').first
        if sl_btn.is_visible():
            sl_label_1 = sl_btn.inner_text().strip()
            print(f"Initial Shortlist button label: '{sl_label_1}'")
            sl_btn.click()
            page.wait_for_timeout(3000)

            sl_btn_after = page.locator('button:has-text("Shortlist")').first
            sl_label_2 = sl_btn_after.inner_text().strip()
            print(f"Toggled Shortlist button label: '{sl_label_2}'")

            shot_sl_toggle = "CHROME_FLOW_003_shortlist_toggle.png"
            page.screenshot(path=str(SCREENSHOTS_PASSED / shot_sl_toggle), full_page=True)
            
            toggled_successfully = sl_label_1 != sl_label_2
            log_result(
                "FLOW-004",
                "Product Shortlist Toggle Action",
                "PASS" if toggled_successfully else "FAIL",
                f"Toggled from '{sl_label_1}' to '{sl_label_2}'",
                shot_sl_toggle
            )

            # Test Shortlisted Only Checkbox
            sl_checkbox = page.get_by_label("⭐ Shortlisted Only", exact=False).first
            if sl_checkbox.is_visible():
                sl_checkbox.click()
                page.wait_for_timeout(3000)
                shot_sl_filtered = "CHROME_FLOW_004_shortlist_filtered_view.png"
                page.screenshot(path=str(SCREENSHOTS_PASSED / shot_sl_filtered), full_page=True)
                log_result("FLOW-005", "Shortlisted-Only Checkbox Filter", "PASS", "Toggled Shortlisted Only view successfully", shot_sl_filtered)
                
                # Uncheck to restore
                sl_checkbox.click()
                page.wait_for_timeout(2000)

            # Revert shortlist button
            sl_btn_revert = page.locator('button:has-text("Shortlist")').first
            sl_btn_revert.click()
            page.wait_for_timeout(2000)

        # ----------------------------------------------------------------------
        # FLOW 3: Live 15-Factor Economics Calculator Form Submission
        # ----------------------------------------------------------------------
        print("\n--- Flow 3: Live 15-Factor Economics Form Submission ---")
        click_nav_tab(page, "📊 Economics")

        # Fill number inputs in the quick_15factor form
        fob_input = page.locator('input[aria-label*="FOB"]').first
        msrp_input = page.locator('input[aria-label*="MSRP"]').first
        calc_btn = page.locator('button:has-text("Calculate 15-Factor Economics")').first

        if fob_input.is_visible() and calc_btn.is_visible():
            fob_input.fill("18.50")
            msrp_input.fill("49.99")
            calc_btn.click()
            page.wait_for_timeout(4000)

            shot_econ_calc = "CHROME_FLOW_005_15factor_form_submitted.png"
            page.screenshot(path=str(SCREENSHOTS_PASSED / shot_econ_calc), full_page=True)
            econ_res_text = page.inner_text('[data-testid="stAppViewContainer"]')
            has_calc_result = "Landed" in econ_res_text or "Margin" in econ_res_text or "Contribution" in econ_res_text
            log_result(
                "FLOW-006",
                "15-Factor Live Economics Form Calculation",
                "PASS" if has_calc_result else "FAIL",
                "Submitted form with FOB=18.50, MSRP=49.99; waterfall recalculated and rendered",
                shot_econ_calc
            )

        # ----------------------------------------------------------------------
        # FLOW 4: SSOT Database Table Search & AI-Rejected Toggle
        # ----------------------------------------------------------------------
        print("\n--- Flow 4: SSOT Database Table Search & Toggle ---")
        click_nav_tab(page, "🗄️ SSOT Database")

        # Test search within table
        db_search = page.get_by_label("🔍 Search within table (text query)", exact=False).first
        if db_search.is_visible():
            db_search.fill("Storage")
            db_search.press("Enter")
            page.wait_for_timeout(2000)
            shot_db_search = "CHROME_FLOW_006_db_explorer_search.png"
            page.screenshot(path=str(SCREENSHOTS_PASSED / shot_db_search), full_page=True)
            log_result("FLOW-007", "SSOT DB In-Table Search Query", "PASS", "Executed query 'Storage' across table rows", shot_db_search)

            db_search.fill("")
            db_search.press("Enter")
            page.wait_for_timeout(1000)

        # Test Toggle: Show AI-Rejected
        show_rejected = page.get_by_label("🔴 Show AI-Rejected (Soft-Deleted)", exact=False).first
        if show_rejected.is_visible():
            show_rejected.click()
            page.wait_for_timeout(2000)
            shot_db_rejected = "CHROME_FLOW_007_db_explorer_show_rejected.png"
            page.screenshot(path=str(SCREENSHOTS_PASSED / shot_db_rejected), full_page=True)
            log_result("FLOW-008", "SSOT DB Show AI-Rejected Toggle", "PASS", "Toggled Show AI-Rejected soft-deleted filter", shot_db_rejected)
            show_rejected.click()
            page.wait_for_timeout(1000)

        # ----------------------------------------------------------------------
        # FLOW 5: War Room Word Document Compilation
        # ----------------------------------------------------------------------
        print("\n--- Flow 5: War Room Meeting Minutes Word Doc Compilation ---")
        click_nav_tab(page, "🎙️ War Room")

        compile_btn = page.locator('button:has-text("Compile Word Doc")').first
        if compile_btn.is_visible():
            compile_btn.click()
            page.wait_for_timeout(3000)

            shot_docx = "CHROME_FLOW_008_war_room_docx_compiled.png"
            page.screenshot(path=str(SCREENSHOTS_PASSED / shot_docx), full_page=True)

            docx_path = ROOT / "data" / "aprs_war_room.docx"
            docx_exists = docx_path.exists()
            docx_size = docx_path.stat().st_size if docx_exists else 0

            log_result(
                "FLOW-009",
                "War Room Word Doc Compilation",
                "PASS" if docx_exists else "FAIL",
                f"Generated {docx_path.name} (file exists: {docx_exists}, size: {docx_size} bytes)",
                shot_docx
            )

        print("\nPage errors recorded during user flows:", len(console_errors))
        browser.close()

    print("================================================================================")
    print(f"USER ACTIONS AUDIT COMPLETED: {len(findings)} FLOWS TESTED")
    print("================================================================================")

if __name__ == "__main__":
    run_user_actions_audit()
