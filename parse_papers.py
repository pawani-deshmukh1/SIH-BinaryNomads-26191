import json
import os

files = ['flood_papers.json', 'lvi_papers.json', 'evac_papers.json']
for f in files:
    print(f"\n--- {f} ---")
    path = os.path.join(r"C:\Users\Ashutosh\Desktop\DISHA", f)
    with open(path, 'r', encoding='utf-16') as fp:
        data = json.load(fp)
        for p in data['results']:
            print(f"- {p.get('display_name')} ({p.get('publication_year')}) [Citations: {p.get('cited_by_count')}]")
