import urllib.request, json

# Check if server is up
try:
    resp = urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)
    print('Backend: UP -', resp.read().decode())
except Exception as e:
    print('Backend: DOWN -', e)
    exit(1)

# Check simulation endpoint
resp = urllib.request.urlopen('http://127.0.0.1:8000/simulation/HAB_BISWANATH_FOREST_002', timeout=30)
data = json.loads(resp.read().decode('utf-8'))

stages = data.get('stages', [])
print('Stages count:', len(stages))
print()
for s in stages:
    fc = s.get('geojson')
    has_base = False
    base_val = None
    if fc and fc.get('features'):
        props = fc['features'][0].get('properties', {})
        has_base = 'base_elevation_m' in props
        base_val = props.get('base_elevation_m')
    label = s['stage_label']
    wl = s['water_level_m']
    print(f'  {label}: water={wl}m, geojson={fc is not None}, base_elevation_m={base_val} (present={has_base})')

ls = data.get('landslide_cone', {})
print()
print('Landslide epicenter:', ls.get('epicenter'))
print('Landslide stages:', len(ls.get('stages', [])))
