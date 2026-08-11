# -*- coding: utf-8 -*-
import json, datetime

with open(r'C:\개인\wooahouse\wootide\_data\raw_all_stations.json', encoding='utf-8') as f:
    raw = json.load(f)

TYPE_MAP = {
    '1': ('high', '만조'), '2': ('low', '간조'),
    '3': ('high', '만조'), '4': ('low', '간조'),
}
DOW = ['월', '화', '수', '목', '금', '토', '일']
TODAY_STR = '2026-08-11'

output = []
for st in raw:
    day_ranges = []
    for day_items in st['days']:
        vals = [float(it['predcTdlvVl']) for it in day_items]
        day_ranges.append(max(vals) - min(vals) if vals else 0)
    min_r, max_r = min(day_ranges), max(day_ranges)

    tide_days = []
    for day_items, rng in zip(st['days'], day_ranges):
        date_str = day_items[0]['predcDt'][:10]
        dt = datetime.date.fromisoformat(date_str)
        ratio = (rng - min_r) / (max_r - min_r) if max_r > min_r else 0.5
        mulddae = round(1 + ratio * 13)

        events = []
        for it in day_items:
            typ, label = TYPE_MAP.get(it.get('extrSe', ''), ('high', '만조'))
            events.append({
                'type': typ, 'typeLabel': label, 'time': it['predcDt'][11:16],
                'val': str(int(float(it['predcTdlvVl'])))
            })

        tide_days.append({
            'dateLabel': dt.strftime('%m/%d'),
            'dow': DOW[dt.weekday()] + '요일',
            'isToday': date_str == TODAY_STR,
            'mulddae': mulddae,
            'events': events,
        })

    extrm = st['extrm_recent']
    if extrm:
        last = extrm[-1]
        yr_max, yr_max_dt = last.get('yrMaxHiwlv', ''), last.get('yrMaxHiwlvDt', '')
        yr_min, yr_min_dt = last.get('yrMinLowlv', ''), last.get('yrMinLowlvDt', '')
    else:
        yr_max = yr_max_dt = yr_min = yr_min_dt = ''

    output.append({
        'slug': st['name'],
        'spotName': st['name'],
        'obsCode': st['code'],
        'region': st['region'],
        'regionSlug': st['regionSlug'],
        'city': st['city'],
        'baseName': st['name'],
        'lot': st['lot'],
        'lat': st['lat'],
        'tideDays': tide_days,
        'yrMax': yr_max,
        'yrMaxDt': yr_max_dt,
        'yrMin': yr_min,
        'yrMinDt': yr_min_dt,
    })

with open(r'C:\개인\wooahouse\wootide\_data\tide_spots.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=1)

print('저장 완료:', len(output), '개 지점')
regions = {}
for o in output:
    regions[o['regionSlug']] = regions.get(o['regionSlug'], 0) + 1
print(regions)
