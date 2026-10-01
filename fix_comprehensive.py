with open('web/app.py', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
new_lines = []

for i, line in enumerate(lines):
    spaces = len(line) - len(line.lstrip(b' \t'))
    stripped = line.lstrip(b' \t')
    
    # Fix the btn_reseed block (inside with sc3: at 12 spaces)
    # if btn_reseed: should be at 12, body at 16
    if i >= 1152 and i <= 1159:  # lines 1153-1160
        if b'if btn_reseed:' in line and spaces == 12:
            new_lines.append(line)
            continue
        elif spaces == 12 and not stripped.startswith(b'#') and stripped:
            # Body should be at 16
            new_lines.append(b'    ' + line)
            continue
    
    # Fix btn_run_scan block (inside with sc3: at 12 spaces)
    # if btn_run_scan...: should be at 12, first level body at 16
    if i >= 1161 and i <= 1170:  # lines 1162-1171
        if b'if btn_run_scan and scan_query.strip():' in line and spaces == 12:
            new_lines.append(line)
            continue
        elif b'user = st.session_state.get' in line and spaces == 12:
            new_lines.append(b'    ' + line)
            continue
        elif b'svc = st.session_state' in line and spaces == 12:
            new_lines.append(b'    ' + line)
            continue
        elif b'if not user:' in line and spaces == 12:
            new_lines.append(b'    ' + line)
            continue
        elif spaces == 12 and (b'st.error' in line or b'show_login' in line or b'st.rerun' in line):
            new_lines.append(b'    ' + line)
            continue
        elif b'else:' in line and spaces == 12:
            new_lines.append(b'    ' + line)
            continue
    
    # Inside else block of btn_run_scan (should be at 16 spaces for first level)
    # try: at 16, body at 20
    if i >= 1171 and i <= 1183:  # lines 1172-1184
        if b'try:' in line and spaces == 16:
            new_lines.append(line)
            continue
        elif b'# Check and consume usage' in line and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif (b'usage_result' in line or b'st.session_state["usage_status"]' in line or b'st.success' in line) and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif b'except Exception as e:' in line and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif (b'if "USAGE_LIMIT_REACHED"' in line or b'st.error' in line or b'st.session_state["show_pricing"]' in line or b'st.rerun()' in line) and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif b'else:' in line and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif b'st.error(f"Usage check failed' in line and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif b'st.stop()' in line and spaces == 16:
            new_lines.append(b'    ' + line)
            continue
        elif b'# Run the swarm scan' in line and spaces == 16:
            new_lines.append(line)
            continue
    
    # with st.status block (should be at 16)
    if i >= 1185 and i <= 1300:
        if b'with st.status' in line and spaces == 16:
            new_lines.append(line)
            continue
        elif spaces == 16 and (b'st.write' in line or b'from core' in line or b'from tools' in line or b'orch =' in line or b'# Gate' in line or b'flaw_prompt' in line or b'nim_res' in line or b'v2_text' in line or b'Gate 3' in line or b'fob_estimate' in line or b'econ_result' in line or b'landed =' in line or b'gross_pct' in line or b'net_pct' in line or b'stress_pct' in line or b'econ_pass' in line or b'econ_score' in line or b'st.write' in line or b'hub =' in line):
            new_lines.append(line)
            continue
    
    new_lines.append(line)

content = b'\n'.join(new_lines)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed all')