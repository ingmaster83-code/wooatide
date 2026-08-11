# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, json, datetime, re, sys, time
sys.path.insert(0, r'C:\개인\wooahouse\wootide\scripts')
from stations import STATIONS

KEY = '9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86'
BASE = 'https://apis.data.go.kr/1192136'
TODAY = datetime.date(2026, 8, 11)

def call(url, params, retries=3):
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

for i, (code, name, region, regionSlug, city) in enumerate(STATIONS):
    try:
        # 8일 고,저조
        days = []
        for d in range(8):
            date_str = (TODAY + datetime.timedelta(days=d)).strftime('%Y%m%d')
            xml = call(f'{BASE}/tideFcstHghLw/GetTideFcstHghLwApiService',
                       {'serviceKey': KEY, 'numOfRows': '10', 'pageNo': '1', 'dataType': 'JSON', 'obsCode': code, 'reqDate': date_str})
            items = parse_items(xml)
            if not items:
                raise ValueError(f'no items for {code} {date_str}: {xml[:200]}')
            days.append(items)

        # 최극조위 최근 (totalCount 확인 후 마지막 페이지)
        xml0 = call(f'{BASE}/extrmTideLvl/GetExtrmTideLvlApiService',
                    {'serviceKey': KEY, 'numOfRows': '1', 'pageNo': '1', 'dataType': 'JSON', 'obsCode': code})
        tc_m = re.search(r'<totalCount>(\d+)</totalCount>', xml0)
        total = int(tc_m.group(1)) if tc_m else 0
        extrm_items = []
        if total > 0:
            last_page = max(1, (total // 300))
            xml1 = call(f'{BASE}/extrmTideLvl/GetExtrmTideLvlApiService',
                        {'serviceKey': KEY, 'numOfRows': '300', 'pageNo': str(last_page), 'dataType': 'JSON', 'obsCode': code})
            extrm_items = parse_items(xml1)

        results.append({
            'code': code, 'name': name, 'region': region, 'regionSlug': regionSlug, 'city': city,
            'lot': days[0][0]['lot'], 'lat': days[0][0]['lat'],
            'days': days,
            'extrm_recent': extrm_items[-12:] if extrm_items else [],
        })
        print(f'[{i+1}/{len(STATIONS)}] OK {code} {name}')
    except Exception as e:
        errors.append((code, name, str(e)))
        print(f'[{i+1}/{len(STATIONS)}] FAIL {code} {name}: {e}')

with open(r'C:\개인\wooahouse\wootide\_data\raw_all_stations.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False)

print(f'\n완료: {len(results)}개 성공, {len(errors)}개 실패')
if errors:
    for c, n, e in errors:
        print(' 실패:', c, n, e)
