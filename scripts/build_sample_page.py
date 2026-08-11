# -*- coding: utf-8 -*-
import json, datetime

with open(r'C:\개인\wooahouse\wootide\_data\yeosu_sample.json', encoding='utf-8') as f:
    data = json.load(f)

TYPE_MAP = {
    '1': ('high', '만조'), '2': ('low', '간조'),
    '3': ('high', '만조'), '4': ('low', '간조'),
}
DOW = ['월', '화', '수', '목', '금', '토', '일']

today_str = '2026-08-11'

# ---- 8일 물때표 데이터 구성 ----
day_ranges = []
for day_items in data['days']:
    vals = [float(it['predcTdlvVl']) for it in day_items]
    day_ranges.append(max(vals) - min(vals) if vals else 0)
min_r, max_r = min(day_ranges), max(day_ranges)

tide_days = []
for day_items, rng in zip(data['days'], day_ranges):
    date_str = day_items[0]['predcDt'][:10]
    dt = datetime.date.fromisoformat(date_str)
    # 물때 근사치: 조차가 클수록 사리(물때 번호 8~9 부근), 작을수록 조금(물때 번호 1 부근)에 가깝게 매핑
    if max_r > min_r:
        ratio = (rng - min_r) / (max_r - min_r)
    else:
        ratio = 0.5
    mulddae = round(1 + ratio * 13)

    events = []
    for it in day_items:
        typ, label = TYPE_MAP.get(it['extrSe'], ('high', '만조'))
        time_str = it['predcDt'][11:16]
        events.append({
            'type': typ, 'typeLabel': label, 'time': time_str,
            'val': str(int(float(it['predcTdlvVl'])))
        })

    tide_days.append({
        'dateLabel': dt.strftime('%m/%d'),
        'dow': DOW[dt.weekday()] + '요일',
        'isToday': date_str == today_str,
        'mulddae': mulddae,
        'events': events,
    })

# ---- 오늘 4칸 카드 ----
today_events = tide_days[0]['events'] if tide_days[0]['isToday'] else []
today_vals = [float(e['val']) for e in today_events]
today_range = int(max(today_vals) - min(today_vals)) if today_vals else 0

# ---- SVG 조위 그래프 (24포인트, 60분 간격) ----
ts = data['timeseries']
vals = [float(p['tdlvHgt']) for p in ts]
vmin, vmax = min(vals), max(vals)
W, H, PAD = 720, 220, 30
n = len(ts)
def x(i): return PAD + (W - 2*PAD) * i / (n - 1)
def y(v): return H - PAD - (H - 2*PAD) * (v - vmin) / (vmax - vmin) if vmax > vmin else H/2

points = ' '.join(f'{x(i):.1f},{y(v):.1f}' for i, v in enumerate(vals))
area_points = f'{PAD},{H-PAD} ' + points + f' {W-PAD},{H-PAD}'

# 시간 축 라벨 (4시간 간격)
labels = []
for i, p in enumerate(ts):
    hh = p['predcDt'][11:13]
    if int(hh) % 4 == 0 and p['predcDt'][14:16] == '00':
        labels.append(f'<text x="{x(i):.1f}" y="{H-8}" font-size="11" fill="#64748B" text-anchor="middle">{hh}시</text>')

svg = f'''<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg">
  <polygon points="{area_points}" fill="#0891B2" opacity="0.12"/>
  <polyline points="{points}" fill="none" stroke="#0891B2" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
  {''.join(labels)}
</svg>'''

svg_escaped = svg.replace('"', '&quot;')

# ---- Front matter 조립 ----
front = {
    'layout': 'spot',
    'title': '여수 물때표 - 오늘 만조·간조 시각 | 우아물때',
    'description': '여수 지역 오늘의 물때표, 만조·간조 시각과 조위를 실시간으로 확인하세요. 국립해양조사원 공식 데이터 기반.',
    'spotName': '여수',
    'region': '전라남도',
    'regionSlug': 'jeonnam',
    'city': '여수시',
    'baseName': data['obsvtrNm'],
    'lot': data['lot'],
    'lat': data['lat'],
    'todayMulddae': f"{tide_days[0]['mulddae']}물",
    'lunarDate': '음력 6월 29일',
    'todayRange': today_range,
    'yrMax': data['yr_max'],
    'yrMaxDt': data['yr_max_dt'],
    'yrMin': data['yr_min'],
    'yrMinDt': data['yr_min_dt'],
}

lines = ['---']
for k, v in front.items():
    if isinstance(v, str) and (':' in v or v.startswith('#')):
        lines.append(f'{k}: "{v}"')
    else:
        lines.append(f'{k}: {v}')

lines.append('todayTides:')
for e in today_events:
    lines.append(f"  - label: \"{e['typeLabel']}\"")
    lines.append(f"    type: {e['type']}")
    lines.append(f"    time: \"{e['time']}\"")
    lines.append(f"    val: {e['val']}")

lines.append('tideDays:')
for d in tide_days:
    lines.append(f"  - dateLabel: \"{d['dateLabel']}\"")
    lines.append(f"    dow: \"{d['dow']}\"")
    lines.append(f"    isToday: {str(d['isToday']).lower()}")
    lines.append(f"    mulddae: {d['mulddae']}")
    lines.append('    events:')
    for e in d['events']:
        lines.append(f"      - type: {e['type']}")
        lines.append(f"        typeLabel: \"{e['typeLabel']}\"")
        lines.append(f"        time: \"{e['time']}\"")
        lines.append(f"        val: {e['val']}")

lines.append('same_region:')
for name, slug in [('완도', 'wando'), ('통영', 'tongyeong'), ('거제도', 'geoje')]:
    lines.append(f'  - name: "{name}"')
    lines.append(f'    slug: "{slug}"')

lines.append('nearby_suggestions:')
for name, slug in [('부산', 'busan'), ('통영', 'tongyeong'), ('완도', 'wando')]:
    lines.append(f'  - name: "{name}"')
    lines.append(f'    slug: "{slug}"')

lines.append(f'chartSvg: |')
for l in svg.split('\n'):
    lines.append('  ' + l)

lines.append('---')

with open(r'C:\개인\wooahouse\wootide\spot\여수\index.html', 'w', encoding='utf-8') as f:
    f.write('\n'.join(lines) + '\n')

print('written, tide_days count:', len(tide_days))
print('today mulddae:', tide_days[0]['mulddae'], 'range:', today_range)
