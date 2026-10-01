with open('web/app.py', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
new_lines = []

for i, line in enumerate(lines):
    spaces = len(line) - len(line.lstrip(b' \t'))
    stripped = line.lstrip(b' \t')
    
    # Fix: body of try: at 20 spaces should be at 24 spaces
    # This applies to lines inside the else block of btn_run_scan
    if i >= 1172 and i <= 1175:  # Lines 1173-1175 (0-indexed: 1172-1174)
        if line.startswith(b'                    ') and not line.startswith(b'                        '):
            # 20 spaces -> 24 spaces
            new_lines.append(b'    ' + line)
            continue
    
    # Fix: except: at 16 spaces should be at 20 spaces (matching try: at 20)
    if i == 1175:  # Line 1176
        if line.startswith(b'                except Exception as e:'):
            new_lines.append(b'    ' + line)
            continue
    
    # Fix: body of except/if/else inside except should be at 24 spaces
    if i >= 1176 and i <= 1182:  # Lines 1177-1183
        if line.startswith(b'                    ') and not line.startswith(b'                        '):
            new_lines.append(b'    ' + line)
            continue
    
    # Fix: else: at line 1181 should be at 20 spaces
    if i == 1180:  # Line 1181
        if line.startswith(b'                    else:'):
            new_lines.append(b'    ' + line)
            continue
    
    # Fix: st.stop() at line 1183 should be at 20 spaces
    if i == 1182:  # Line 1183
        if line.startswith(b'                    st.stop()'):
            new_lines.append(b'    ' + line)
            continue
    
    new_lines.append(line)

content = b'\n'.join(new_lines)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed')