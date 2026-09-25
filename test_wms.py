import requests
import xml.etree.ElementTree as ET
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_layers(name, url):
    try:
        res = requests.get(f"{url}?service=WMS&request=GetCapabilities", verify=False, timeout=15)
        root = ET.fromstring(res.text)
        # Find all Layer/Name elements (namespace might vary, doing simple text search if needed, or xpath)
        layers = []
        for elem in root.iter():
            if elem.tag.endswith('Layer'):
                for child in elem:
                    if child.tag.endswith('Name') and child.text:
                        layers.append(child.text)
        print(f"[{name}] Found {len(layers)} layers. First 10: {layers[:10]}")
    except Exception as e:
        print(f"[{name}] Error: {e}")

get_layers("Bhuvan", "https://bhuvan-vec1.nrsc.gov.in/bhuvan/wms")
get_layers("INCOIS", "https://erddap.incois.gov.in/erddap/wms/INCOIS_SST_L4_PDAY/request") # Just trying another guessed base
