import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    response = requests.get("https://erddap.incois.gov.in/erddap/info/index.json", verify=False, timeout=10)
    print(f"[INCOIS ERDDAP] Status: {response.status_code}")
except Exception as e:
    print(f"[INCOIS ERDDAP] ERROR: {str(e)}")
