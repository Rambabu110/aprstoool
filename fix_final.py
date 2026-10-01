with open('web/app.py', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
new_lines = []

for i, line in enumerate(lines):
    spaces = len(line) - len(line.lstrip(b' \t'))
    
    # Fix body of 'with st.status' (should be at 20 spaces inside the with at 16)
    # This applies from the line after 'with st.status' until the matching dedent
    if i >= 1186 and i <= 1250:
        if b'with st.status' in line and spaces == 16:
            new_lines.append(line)
            continue
        elif spaces == 16 and (b'st.write' in line or b'from core' in line or b'from tools' in line or b'try:' in line):
            # These should be at 20 spaces (inside with block)
            new_lines.append(b'    ' + line)
            continue
        elif spaces == 20 and (b'scraper =' in line or b'live_items' in line or b'st.write' in line or b'from core' in line or b'from tools' in line or b'# Gate' in line or b'flaw_prompt' in line or b'nim_res' in line or b'v2_text' in line or b'Gate 3' in line or b'fob_estimate' in line or b'econ_result' in line or b'landed =' in line or b'gross_pct' in line or b'net_pct' in line or b'stress_pct' in line or b'econ_pass' in line or b'econ_score' in line or b'st.write' in line or b'hub =' in line):
            new_lines.append(line)
            continue
        elif spaces == 16 and b'# Gate' in line:
            new_lines.append(b'    ' + line)
            continue
        elif spaces == 16 and (b'except Exception' in line or b'status.update' in line or b'st.cache_data' in line or b'st.toast' in line or b'time.sleep' in line or b'st.rerun' in line):
            new_lines.append(b'    ' + line)
            continue
        elif spaces == 20 and (b'st.error' in line or b'st.success' in line or b'st.write' in line):
            # Inside try/except in with block
            new_lines.append(line)
            continue
        elif spaces == 16 and (b'else:' in line or b'if econ_pass' in line):
            new_lines.append(b'    ' + line)
            continue
        elif spaces == 20 and (b'update_gate_status' in line or b'status.update' in line):
            new_lines.append(line)
            continue
        else:
            new_lines.append(line)
    else:
        new_lines.append(line)

content = b'\n'.join(new_lines)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed all indentation')