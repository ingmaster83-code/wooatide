# -*- coding: utf-8 -*-
import csv, re, json

with open(r'C:\개인\wooahouse\wootide\_data\so_stations.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

seen = {}
for r in rows:
    lat = round(float(r['위도']), 3)
    lot = round(float(r['경도']), 3)
    key = (lat, lot)
    name = re.sub(r'^\d{4}년[_ ]?', '', r['관측지점 명']).strip()
    entry = {'code': r['관측지점 코드명'], 'name': name, 'lat': r['위도'], 'lot': r['경도'], 'year': r['관측연도']}
    if key not in seen or int(r['관측연도']) > int(seen[key]['year']):
        seen[key] = entry

stations = list(seen.values())
with open(r'C:\개인\wooahouse\wootide\_data\extended_stations.json', 'w', encoding='utf-8') as f:
    json.dump(stations, f, ensure_ascii=False, indent=1)

print('unique:', len(stations))
