# -*- coding: utf-8 -*-
import json

with open(r'C:\개인\wooahouse\wootide\_data\tide_spots.json', encoding='utf-8') as f:
    official_spots = json.load(f)

def nearest_official_spot(lot, lat):
    best, best_d = None, None
    for s in official_spots:
        d = (float(s['lot']) - lot) ** 2 + (float(s['lat']) - lat) ** 2
        if best_d is None or d < best_d:
            best, best_d = s, d
    return best

def load(path):
    try:
        with open(path, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return []

raw = load(r'C:\개인\wooahouse\wootide\_data\raw_extended.json') + load(r'C:\개인\wooahouse\wootide\_data\raw_extended_retry.json')
print('총 원본 항목:', len(raw))

output = []
for st in raw:
    series = sorted(st['series'], key=lambda x: x['slctdDt'])
    if len(series) < 3:
        continue

    pts = [(p['slctdDt'][11:16], float(p['slctdHgt'])) for p in series]
    vals = [v for _, v in pts]

    # 로컬 극값(고조/저조) 탐지
    events = []
    for i in range(len(pts)):
        prev_v = vals[i - 1] if i > 0 else None
        next_v = vals[i + 1] if i < len(pts) - 1 else None
        is_max = (prev_v is None or vals[i] >= prev_v) and (next_v is None or vals[i] >= next_v)
        is_min = (prev_v is None or vals[i] <= prev_v) and (next_v is None or vals[i] <= next_v)
        if i == 0 or i == len(pts) - 1:
            continue  # 하루의 시작/끝은 제외 (경계값 왜곡 방지)
        if is_max and not is_min:
            events.append({'type': 'high', 'typeLabel': '만조', 'time': pts[i][0], 'val': str(round(vals[i]))})
        elif is_min and not is_max:
            events.append({'type': 'low', 'typeLabel': '간조', 'time': pts[i][0], 'val': str(round(vals[i]))})

    if not events:
        continue

    # TideBED가 실제로 조위 계산에 사용한 기준항 (정확도 표기용)
    base_name = series[0]['obsvtrNm']
    lot_f, lat_f = float(st['lot']), float(st['lat'])

    # 지역 분류·안내 링크용: 좌표상 가장 가까운 "우리가 페이지를 만든" 공식 지점
    nearest = nearest_official_spot(lot_f, lat_f)

    output.append({
        'slug': st['slug'],
        'spotName': st['name'],
        'baseName': base_name,
        'baseSlug': nearest['slug'],
        'nearestOfficialName': nearest['spotName'],
        'region': nearest['region'],
        'regionSlug': nearest['regionSlug'],
        'city': nearest['city'],
        'lot': str(round(lot_f, 5)),
        'lat': str(round(lat_f, 5)),
        'todayEvents': events,
        'todaySeries': [{'time': t, 'val': str(round(v))} for t, v in pts],
    })

with open(r'C:\개인\wooahouse\wootide\_data\extended_spots.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=1)

print('처리 완료:', len(output), '개 지점')
no_base = [o for o in output if not o['baseSlug']]
print('기준항 매칭 실패:', len(no_base))
