with open('web/app.py', 'rb') as f:
    content = f.read()

lines = content.split(b'\n')
new_lines = []

for i, line in enumerate(lines):
    spaces = len(line) - len(line.lstrip(b' \t'))
    
    # Fix try: body inside with st.status block
    # try: at 20 spaces -> body at 24 spaces
    if i >= 1190 and i <= 1200:
        if b'try:' in line and spaces == 20:
            new_lines.append(line)
            continue
        elif spaces == 20 and (b'# Search' in line or b'scraper =' in line or b'live_items' in line or b'st.write' in line):
            new_lines.append(b'    ' + line)
            continue
        elif b'from core.database import' in line and spaces == 0:
            new_lines.append(b'                    ' + line)
            continue
        elif b'from core.database import' in line and spaces == 20:
            new_lines.append(b'    ' + line)
            continue
        elif b'from core.database import' in line and spaces == 24:
            new_lines.append(line)
            continue
        elif b'from core.database import' in line and spaces == 20:
            new_lines.append(b'    ' + line)
            continue
        elif b'record_product_evaluation' in line and spaces == 24:
            new_lines.append(line)
            continue
        elif b'record_defect_cluster' in line and spaces == 24:
            new_lines.append(line)
            continue
        elif b')' in line and line.strip() == b')' and spaces == 20:
            new_lines.append(b'    ' + line)
            continue
    
    new_lines.append(line)

content = b'\n'.join(new_lines)

with open('web/app.py', 'wb') as f:
    f.write(content)
print('Fixed try body')