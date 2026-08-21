# -*- coding: utf-8 -*-
"""매일 실행: 56개 공식 지점 + 256개 확장 지점의 물때 데이터를 최신으로 갱신한다.
기존 _data/tide_spots.json, _data/extended_spots.json을 그 자리에서 덮어쓴다.
GitHub Actions 스케줄(cron)에서 실행되는 것을 전제로, 실패한 확장지점은
이전 데이터를 그대로 유지해 사이트가 깨지지 않도록 한다."""
import urllib.request, urllib.parse, json, datetime, re, sys, time, os

KEY = '9490b1d34e92aa9e25b32a4cff1438fc7b9c71e5d332413916a391e867f61e86'
BASE = 'https://apis.data.go.kr/1192136'
WTEM_BASE = 'https://apis.data.go.kr/1192136/surveyWaterTemp'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TODAY = datetime.date.today()
TODAY_STR = TODAY.strftime('%Y-%m-%d')
DOW = ['월', '화', '수', '목', '금', '토', '일']
TYPE_MAP = {'1': ('high', '만조'), '2': ('low', '간조'), '3': ('high', '만조'), '4': ('low', '간조')}


def call(url, params, retries=3):
    full = url + '?' + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(full, timeout=20) as resp:
                return resp.read().decode('utf-8')
        except Exception:
            if attempt == retries - 1:
                return None
            time.sleep(2 * (attempt + 1))
    return None


def parse_items(xml):
    if not xml:
        return []
    items = re.findall(r'<item>(.*?)</item>', xml, re.S)
    out = []
    for it in items:
        d = {}
        for tag, val in re.findall(r'<(\w+)>([^<]*)</\1>', it):
            d[tag] = val
        out.append(d)
    return out


def refresh_official():
    path = os.path.join(ROOT, '_data', 'tide_spots.json')
    with open(path, encoding='utf-8') as f:
        spots = json.load(f)

    ok, fail = 0, 0
    for sp in spots:
        code = sp['obsCode']
        try:
            days = []
            for d in range(8):
                date_str = (TODAY + datetime.timedelta(days=d)).strftime('%Y%m%d')
                xml = call(f'{BASE}/tideFcstHghLw/GetTideFcstHghLwApiService',
                           {'serviceKey': KEY, 'numOfRows': '10', 'pageNo': '1', 'dataType': 'JSON',
                            'obsCode': code, 'reqDate': date_str})
                items = parse_items(xml)
                if not items:
                    raise ValueError(f'no items for {date_str}')
                days.append(items)

            day_ranges = []
            for day_items in days:
                vals = [float(it['predcTdlvVl']) for it in day_items]
                day_ranges.append(max(vals) - min(vals) if vals else 0)
            min_r, max_r = min(day_ranges), max(day_ranges)

            tide_days = []
            for day_items, rng in zip(days, day_ranges):
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
                    'dateLabel': dt.strftime('%m/%d'), 'dow': DOW[dt.weekday()] + '요일',
                    'isToday': date_str == TODAY_STR, 'mulddae': mulddae, 'events': events,
                })
            sp['tideDays'] = tide_days
            sp['lot'], sp['lat'] = days[0][0]['lot'], days[0][0]['lat']

            xml0 = call(f'{BASE}/extrmTideLvl/GetExtrmTideLvlApiService',
                        {'serviceKey': KEY, 'numOfRows': '1', 'pageNo': '1', 'dataType': 'JSON', 'obsCode': code})
            tc_m = re.search(r'<totalCount>(\d+)</totalCount>', xml0 or '')
            total = int(tc_m.group(1)) if tc_m else 0
            if total > 0:
                last_page = max(1, (total // 300))
                xml1 = call(f'{BASE}/extrmTideLvl/GetExtrmTideLvlApiService',
                            {'serviceKey': KEY, 'numOfRows': '300', 'pageNo': str(last_page),
                             'dataType': 'JSON', 'obsCode': code})
                extrm_items = parse_items(xml1)
                if extrm_items:
                    last = extrm_items[-1]
                    sp['yrMax'] = last.get('yrMaxHiwlv', sp.get('yrMax', ''))
                    sp['yrMaxDt'] = last.get('yrMaxHiwlvDt', sp.get('yrMaxDt', ''))
                    sp['yrMin'] = last.get('yrMinLowlv', sp.get('yrMin', ''))
                    sp['yrMinDt'] = last.get('yrMinLowlvDt', sp.get('yrMinDt', ''))
            ok += 1
        except Exception as e:
            fail += 1
            print(f'  [공식/실패] {sp["spotName"]}: {e} (이전 데이터 유지)')
        time.sleep(0.3)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=1)
    print(f'공식 지점: {ok}개 갱신, {fail}개 실패(유지)')


def fetch_latest_water_temp(code):
    """조위관측소 실측 수온 API에서 obsCode의 가장 최근 측정값 1건을 가져온다."""
    xml0 = call(f'{WTEM_BASE}/GetSurveyWaterTempApiService',
                {'serviceKey': KEY, 'numOfRows': '1', 'pageNo': '1', 'dataType': 'JSON', 'obsCode': code})
    tc_m = re.search(r'<totalCount>(\d+)</totalCount>', xml0 or '')
    total = int(tc_m.group(1)) if tc_m else 0
    if total < 1:
        return None
    xml1 = call(f'{WTEM_BASE}/GetSurveyWaterTempApiService',
                {'serviceKey': KEY, 'numOfRows': '1', 'pageNo': str(total), 'dataType': 'JSON', 'obsCode': code})
    items = parse_items(xml1)
    if not items:
        return None
    it = items[0]
    return {'wtem': it.get('wtem', ''), 'obsrvnDt': it.get('obsrvnDt', '')}


def refresh_water_temp():
    """56개 공식 지점의 실측 수온을 갱신하고, 확장지점(nearestOfficialName)에도 전파한다."""
    path = os.path.join(ROOT, '_data', 'tide_spots.json')
    with open(path, encoding='utf-8') as f:
        spots = json.load(f)

    wtem_by_name = {}
    ok, fail = 0, 0
    for sp in spots:
        try:
            result = fetch_latest_water_temp(sp['obsCode'])
            if not result or not result['wtem']:
                raise ValueError('no water temp data')
            sp['waterTemp'] = result['wtem']
            sp['waterTempTime'] = result['obsrvnDt']
            wtem_by_name[sp['spotName']] = (result['wtem'], result['obsrvnDt'])
            ok += 1
        except Exception as e:
            fail += 1
            print(f'  [수온/실패] {sp["spotName"]}: {e} (이전 데이터 유지)')
            if sp.get('waterTemp'):
                wtem_by_name[sp['spotName']] = (sp['waterTemp'], sp.get('waterTempTime', ''))
        time.sleep(0.3)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=1)
    print(f'수온(공식 지점): {ok}개 갱신, {fail}개 실패(유지)')

    # 확장지점(nearestOfficialName)에 인근 관측소 수온 전파
    ext_path = os.path.join(ROOT, '_data', 'extended_spots.json')
    with open(ext_path, encoding='utf-8') as f:
        ext_spots = json.load(f)

    propagated = 0
    for sp in ext_spots:
        nearest = sp.get('nearestOfficialName', '')
        if nearest in wtem_by_name:
            sp['waterTemp'], sp['waterTempTime'] = wtem_by_name[nearest]
            propagated += 1

    with open(ext_path, 'w', encoding='utf-8') as f:
        json.dump(ext_spots, f, ensure_ascii=False, indent=1)
    print(f'수온(확장 지점 전파): {propagated}개')


def refresh_extended():
    path = os.path.join(ROOT, '_data', 'extended_spots.json')
    with open(path, encoding='utf-8') as f:
        spots = json.load(f)

    ok, fail = 0, 0
    for sp in spots:
        try:
            xml = call(f'{BASE}/tidebed/GetTidebedApiService',
                       {'serviceKey': KEY, 'numOfRows': '30', 'pageNo': '1', 'dataType': 'JSON',
                        'lot': sp['lot'], 'lat': sp['lat'], 'reqDate': TODAY.strftime('%Y%m%d'), 'min': '60'})
            items = parse_items(xml)
            if len(items) < 3:
                raise ValueError('insufficient series points')

            series = sorted(items, key=lambda x: x['slctdDt'])
            pts = [(p['slctdDt'][11:16], float(p['slctdHgt'])) for p in series]
            vals = [v for _, v in pts]

            events = []
            for i in range(1, len(pts) - 1):
                prev_v, next_v = vals[i - 1], vals[i + 1]
                is_max = vals[i] >= prev_v and vals[i] >= next_v
                is_min = vals[i] <= prev_v and vals[i] <= next_v
                if is_max and not is_min:
                    events.append({'type': 'high', 'typeLabel': '만조', 'time': pts[i][0], 'val': str(round(vals[i]))})
                elif is_min and not is_max:
                    events.append({'type': 'low', 'typeLabel': '간조', 'time': pts[i][0], 'val': str(round(vals[i]))})
            if not events:
                raise ValueError('no high/low events detected')

            sp['todayEvents'] = events
            sp['todaySeries'] = [{'time': t, 'val': str(round(v))} for t, v in pts]
            ok += 1
        except Exception as e:
            fail += 1
            print(f'  [확장/실패] {sp["spotName"]}: {e} (이전 데이터 유지)')
        time.sleep(0.3)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(spots, f, ensure_ascii=False, indent=1)
    print(f'확장 지점: {ok}개 갱신, {fail}개 실패(유지)')


if __name__ == '__main__':
    print(f'=== {TODAY_STR} 물때 데이터 갱신 시작 ===')
    refresh_official()
    refresh_extended()
    refresh_water_temp()
    print('=== 완료 ===')
