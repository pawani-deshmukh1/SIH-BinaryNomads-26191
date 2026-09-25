import json
import sys

with open(r'C:\Users\Ashutosh\.gemini\antigravity-ide\brain\6df347b8-11a5-4ae8-b319-d9d9e71936c2\.system_generated\logs\transcript.jsonl', 'r', encoding='utf-8') as f:
    lines = f.readlines()

keywords = ['layer 2', 'strategic', 'monthly', 'long term', 'gee', 'kaggle coastal', 'runway', 'watchlist', 'coastal extractor', 'coastal erosion', 'strategic monitor', 'time series']
matches = []
for i, line in enumerate(lines):
    try:
        obj = json.loads(line)
        content = (obj.get('content', '') or '').lower()
        t = obj.get('type', '')
        if t in ('USER_INPUT', 'PLANNER_RESPONSE') and any(k in content for k in keywords):
            raw = obj.get('content', '')[:600]
            matches.append((i, t, raw))
    except:
        pass

with open('layer2_search.txt', 'w', encoding='utf-8') as out:
    out.write(f'Total matches: {len(matches)}\n\n')
    for i, t, c in matches:
        out.write(f'--- [{i}] {t} ---\n')
        out.write(c + '\n\n')

print(f"Done. Found {len(matches)} matches. Written to layer2_search.txt")
