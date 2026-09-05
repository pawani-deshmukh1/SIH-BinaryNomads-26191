import zipfile
import re

apk_path = 'app-release.apk'
try:
    with zipfile.ZipFile(apk_path, 'r') as apk:
        print("Files in APK:", len(apk.namelist()))
        dex_files = [f for f in apk.namelist() if f.endswith('.dex')]
        print("DEX files:", dex_files)
        
        urls = set()
        for dex in dex_files:
            data = apk.read(dex)
            found = re.findall(b'https?://[^\s\"\'<>]+', data)
            for u in found:
                urls.add(u.decode('utf-8', errors='ignore'))
                
        print("\nInteresting URLs found in code:")
        for u in sorted(urls):
            u_lower = u.lower()
            if '127.0.0.1' in u_lower or '10.0.2.2' in u_lower or 'localhost' in u_lower or 'disha' in u_lower:
                print("-->", u)
            elif 'google' not in u_lower and 'android' not in u_lower and 'w3.org' not in u_lower and 'apache' not in u_lower and 'github' not in u_lower:
                if len(u) < 100:
                    print("   ", u)
                
        manifest = apk.read('AndroidManifest.xml')
        strings = re.findall(b'[a-zA-Z0-9_.-]{6,}', manifest)
        print("\nInteresting Manifest strings:")
        for s in set(strings):
            s_dec = s.decode('utf-8', errors='ignore')
            if 'permission' in s_dec.lower() or 'disha' in s_dec.lower() or 'activity' in s_dec.lower():
                print(s_dec)

except Exception as e:
    print("Error:", e)
