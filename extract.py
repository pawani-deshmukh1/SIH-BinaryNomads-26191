import json
import sys

transcript_path = r"C:\Users\Ashutosh\.gemini\antigravity-ide\brain\6df347b8-11a5-4ae8-b319-d9d9e71936c2\.system_generated\logs\transcript.jsonl"
out_path = r"C:\Users\Ashutosh\Desktop\DISHA\extracted_index.txt"

with open(transcript_path, 'r', encoding='utf-8') as f, open(out_path, 'w', encoding='utf-8') as out:
    for line in f:
        try:
            data = json.loads(line)
            content = data.get('content', '')
            if content and 'dashboard/index.html' in content:
                out.write(f"--- STEP {data.get('step_index')} [{data.get('type')}] ---\n")
                out.write(content + "\n\n")
            
            tool_calls = data.get('tool_calls', [])
            for tc in tool_calls:
                if tc.get('name') == 'view_file':
                    args = tc.get('args', {})
                    if 'index.html' in str(args):
                        out.write(f"--- STEP {data.get('step_index')} TOOL CALL view_file ---\n")
                        out.write(json.dumps(args) + "\n\n")
                elif tc.get('name') == 'multi_replace_file_content' or tc.get('name') == 'replace_file_content':
                    args = tc.get('args', {})
                    if 'index.html' in str(args):
                        out.write(f"--- STEP {data.get('step_index')} TOOL CALL {tc.get('name')} ---\n")
                        out.write(json.dumps(args) + "\n\n")
        except:
            pass

print("Done")
