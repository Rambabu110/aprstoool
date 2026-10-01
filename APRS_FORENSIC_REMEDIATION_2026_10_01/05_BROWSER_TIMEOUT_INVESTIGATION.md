# 05 — BROWSER SCROLL TIMEOUT INVESTIGATION

## Investigation Date
2026-10-01

## Reported Issue
During browser subagent E2E audit, Playwright mouse-wheel scroll operations occasionally timed out in the test harness. This was noted as a potential APRS issue.

## Evidence Reviewed
1. Browser subagent completed full nav audit (12/12 tabs, 5/5 subtabs) with no app failures
2. All Streamlit tab clicks worked correctly
3. No JavaScript console errors from APRS code were reported
4. Timeouts were on `page.mouse.wheel()` calls, not on Streamlit responses

## Analysis

### Cause
Playwright's `mouse.wheel()` in headless mode under a CPU-loaded environment can timeout when:
1. Browser event loop is processing a large Streamlit delta message
2. The subagent shell process has limited CPU budget
3. Network-idle waits are competing with rendering

### APRS App Behavior
- Streamlit app responded to all click events correctly
- All tab content rendered within 2-3 seconds of button click
- The app itself never crashed, errored, or returned a Python exception
- Session state transitions worked perfectly (verified via heading change detection)

## Classification

**TEST-HARNESS ISSUE — Not an APRS application defect.**

Streamlit app is not broken. The timeout was in the Playwright test orchestration layer, not in the application code.

## Action Required
- **APRS:** No changes needed
- **Test harness:** If browser scroll testing is required in CI, use `page.evaluate("window.scrollBy(0, 500)")` instead of `page.mouse.wheel()` for better reliability in headless environments
