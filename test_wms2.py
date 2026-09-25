import requests

url = "https://coastwatch.pfeg.noaa.gov/erddap/wms/erdAQssta1day/request"
params = {
    "service": "WMS",
    "request": "GetMap",
    "layers": "erdAQssta1day:sst",
    "format": "image/png",
    "transparent": "true",
    "version": "1.3.0",
    "width": "256",
    "height": "256",
    "crs": "EPSG:4326",
    "bbox": "70,10,90,30"
}
try:
    res = requests.get(url, params=params, timeout=10)
    print(res.status_code)
    print(res.headers.get('content-type'))
    if res.status_code != 200:
        print(res.text)
except Exception as e:
    print(e)
