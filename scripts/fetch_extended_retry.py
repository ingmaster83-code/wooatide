# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, json, re, time

KEY = '9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86'
BASE = 'https://apis.data.go.kr/1192136'
TODAY = '20260811'

with open(r'C:\개인\wooahouse\wootide\_data\extended_remaining.json', encoding='utf-8') as f:
    remaining = json.load(f)

def call(url, params, retries=3):
    full = url + '?' + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=20) as resp:
                body = resp.read().decode('utf-8')
            if 'resultCode>00' in body:
                return body
            if 'resultCode>22' in body or 'resultCode>21' in body:
                return 'RATE_LIMIT'
            # invalid param / transient -> longer backoff and retry
            time.sleep(5 * (attempt + 1))
        except Exception:
            time.sleep(5 * (attempt + 1))
    return None

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

for i, e in enumerate(remaining):
    if rate_limited:
        break
    body = call(f'{BASE}/tidebed/GetTidebedApiService',
                {'serviceKey': KEY, 'numOfRows': '30', 'pageNo': '1', 'dataType': 'JSON',
                 'lot': e['lot'], 'lat': e['lat'], 'reqDate': TODAY, 'min': '60'})
    if body == 'RATE_LIMIT':
        print(f'[{i+1}/{len(remaining)}] RATE LIMITED - stopping', flush=True)
        rate_limited = True
        break
    if body is None:
        errors.append((e['slug'], 'exhausted retries'))
    else:
        items = parse_items(body)
        if not items:
            errors.append((e['slug'], body[:150]))
        else:
            results.append({**e, 'series': items})

    if i == 9 and len(results) == 0:
        print('처음 10개 전부 실패 - 조기 중단', flush=True)
        break

    if (i + 1) % 20 == 0:
        print(f'[{i+1}/{len(remaining)}] 진행중... (성공 {len(results)}, 실패 {len(errors)})', flush=True)
    time.sleep(1.5)

with open(r'C:\개인\wooahouse\wootide\_data\raw_extended_retry.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False)

print(f'\n완료: {len(results)}개 성공, {len(errors)}개 실패, rate_limited={rate_limited}')
for s, e in errors[:10]:
    print(' 실패:', s, e)
