with open('web/app.py', 'rb') as f:
    content = f.read()

# Fix: body of 'with st.status' should be at 20 spaces
old = b'                with st.status(f"\xe2\x9a\xa1 Swarm Orchestrating Discovery for \'{scan_query}\' in {scan_regio\r\n                st.write("\xf0\x9f\x94\x8d **Gate 1: Signal Discovery** \xe2\x80\x94 Searching live Amazon listings via T\r\n                from core.orchestrator import AutonomousProductResearchOrchestrator\r\n                from tools.amazon_live_scraper import AmazonLiveScraper\r\n                \r\n                try:'
new = b'                with st.status(f"\xe2\x9a\xa1 Swarm Orchestrating Discovery for \'{scan_query}\' in {scan_regio\r\n                    st.write("\xf0\x9f\x94\x8d **Gate 1: Signal Discovery** \xe2\x80\x94 Searching live Amazon listings via T\r\n                    from core.orchestrator import AutonomousProductResearchOrchestrator\r\n                    from tools.amazon_live_scraper import AmazonLiveScraper\r\n                    \r\n                    try:'

content = content.replace(old, new)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed')