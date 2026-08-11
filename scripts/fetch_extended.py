# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, json, re, sys, time
from collections import Counter
sys.path.insert(0, r'C:\개인\wooahouse\wootide\scripts')
from stations import STATIONS

KEY = '9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86'
BASE = 'https://apis.data.go.kr/1192136'
TODAY = '20260811'

with open(r'C:\개인\wooahouse\wootide\_data\extended_stations.json', encoding='utf-8') as f:
    ext = json.load(f)

official_names = set(s[1] for s in STATIONS)
name_counts = Counter(e['name'] for e in ext)

for e in ext:
    if e['name'] in official_names or name_counts[e['name']] > 1:
        e['slug'] = f"{e['name']}-{e['code']}"
    else:
        e['slug'] = e['name']

def call(url, params, retries=2):
    full = url + '?' + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=20) as resp:
                return resp.read().decode('utf-8')
        except Exception as e:
            if attempt == retries - 1:
                raise
            time.sleep(1)

def parse_items(xml):
    items = re.findall(r'<item>(.*?)</item>', xml, re.S)
    out = []
    for it in items:
        d = {}
        for tag, val in re.findall(r'<(\w+)>([^<]*)</\1>', it):
            d[tag] = val
        out.append(d)
    return out

results = []
errors = []
rate_limited = False

for i, e in enumerate(ext):
    if rate_limited:
        break
    try:
        xml = call(f'{BASE}/tidebed/GetTidebedApiService',
                   {'serviceKey': KEY, 'numOfRows': '30', 'pageNo': '1', 'dataType': 'JSON',
                    'lot': e['lot'], 'lat': e['lat'], 'reqDate': TODAY, 'min': '60'})
        if 'LIMITED_NUMBER_OF_SERVICE_REQUESTS_EXCEEDS_ERROR' in xml or 'resultCode>22' in xml:
            print(f'[{i+1}/{len(ext)}] RATE LIMITED - stopping')
            rate_limited = True
            break
        items = parse_items(xml)
        if not items:
            raise ValueError(f'no items: {xml[:200]}')
        results.append({**e, 'series': items})
        if (i + 1) % 50 == 0:
            print(f'[{i+1}/{len(ext)}] OK so far...')
    except Exception as ex:
        errors.append((e['slug'], str(ex)))

with open(r'C:\개인\wooahouse\wootide\_data\raw_extended.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False)

print(f'\n완료: {len(results)}개 성공, {len(errors)}개 실패, rate_limited={rate_limited}')
for s, e in errors[:10]:
    print(' 실패:', s, e)
