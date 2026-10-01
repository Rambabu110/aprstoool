import json

with open(r'C:\Users\HP\.gemini\antigravity-ide\brain\ec5ff5e7-5df1-42af-b328-53508f1b9a5c\.system_generated\logs\transcript_full.jsonl', 'r', encoding='utf-8') as f:
    for line in f:
        if '"step_index":5011' in line:
            obj = json.loads(line)
            with open('step_5011_prompt.txt', 'w', encoding='utf-8') as out:
                out.write(obj.get('content', ''))
            print('Written step 5011 prompt! Len:', len(obj.get('content', '')))
            break
