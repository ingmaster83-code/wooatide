# -*- coding: utf-8 -*-
"""우아낚시 해안 낚시터/항구/섬/등대/해안절경 + 우아스플래시 해수욕장 좌표로 TideBED 물때를 조회해
_data/extended_spots.json 에 지점을 추가한다. (기존 항목은 건드리지 않음, 재실행해도 중복 추가 안 됨)"""
import json, os, re, sys, time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_refresh import call, parse_items, KEY, BASE, TODAY, DOW  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.dirname(ROOT)

KIND_LABEL = {'sea': '바다낚시터', 'port': '항구·포구', 'island': '섬', 'lighthouse': '등대', 'coast': '해안절경', 'beach': '해수욕장'}


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def clean_name(n):
    n = re.sub(r'^(\(주\)|㈜|\(유\)|\(사\))\s*', '', n.strip())
    return re.sub(r'\s+', ' ', n)


def make_slug(name):
    s = re.sub(r'[^0-9A-Za-z가-힣\-]+', '-', name).strip('-')
    return s


def trim(text, n=110):
    text = re.sub(r'<[^>]+>', ' ', text or '')
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= n:
        return text
    cut = text[:n]
    for sep in ('. ', '다. ', '요. '):
        i = cut.rfind(sep)
        if i > 50:
            return cut[:i + len(sep)].strip()
    return cut.rstrip() + '…'


def parse_list(v):
    if isinstance(v, list):
        return v
    try:
        return json.loads((v or '[]').replace("'", '"'))
    except Exception:
        return []


def fish_blurb(s):
    if s['typeSlug'] == 'sea':
        parts = []
        if s.get('capacity'):
            parts.append(f"수용인원 {s['capacity']}명")
        if s.get('fee'):
            parts.append(f"이용요금 {s['fee']}")
        sp = parse_list(s.get('species'))
        if sp:
            parts.append('대상어종 ' + '·'.join(sp))
        if s.get('convenience'):
            cv = parse_list(s.get('convenience'))
            if cv:
                parts.append('편의시설 ' + '·'.join(cv[:4]))
        return ' / '.join(parts)
    return trim(s.get('point'))


def main():
    official = load(os.path.join(ROOT, '_data', 'tide_spots.json'))
    ext_path = os.path.join(ROOT, '_data', 'extended_spots.json')
    ext = load(ext_path)
    existing = official + ext
    valid_regions = {s['regionSlug'] for s in existing}
    used_names = {s['spotName'] for s in existing}
    used_slugs = {s['slug'] for s in existing}
    used_coords = {(round(float(s['lat']), 4), round(float(s['lot']), 4)) for s in existing}
    added_names = {s['spotName'] for s in ext if s.get('sourceUrl')}

    fish = load(os.path.join(PORTFOLIO, 'wooafish', '_data', 'fishing_spots.json'))
    splash = load(os.path.join(PORTFOLIO, 'wooasplash', '_data', 'splash_spots.json'))

    cands = []
    for s in fish:
        if s['typeSlug'] in ('sea', 'port', 'island', 'lighthouse', 'coast'):
            cands.append({
                'name': clean_name(s['spotName']), 'lat': s['lat'], 'lot': s['lng'], 'region': s['region'],
                'regionSlug': s['regionSlug'], 'city': s['city'], 'address': s.get('address', ''),
                'kind': KIND_LABEL[s['typeSlug']], 'blurb': fish_blurb(s),
                'sourceLabel': '우아낚시', 'sourceUrl': f"https://wooafish.wooahouse.com/spot/{s['slug']}/",
            })
    for s in splash:
        if s['kind'] == 'beach':
            cands.append({
                'name': clean_name(s['spotName']), 'lat': s['lat'], 'lot': s['lng'], 'region': s['region'],
                'regionSlug': s['regionSlug'], 'city': s['city'], 'address': s.get('address', ''),
                'kind': KIND_LABEL['beach'], 'blurb': trim(s.get('overview')),
                'sourceLabel': '우아스플래시', 'sourceUrl': f"https://wooasplash.wooahouse.com/spot/{s['slug']}/",
            })
    print(f'후보 {len(cands)}개')

    picked, skipped = [], {'no_coord': 0, 'region': 0, 'name': 0, 'coord': 0}
    for c in cands:
        try:
            lat, lot = float(c['lat']), float(c['lot'])
        except (TypeError, ValueError):
            skipped['no_coord'] += 1
            continue
        if c['regionSlug'] not in valid_regions:
            skipped['region'] += 1
            continue
        if c['name'] in used_names or c['name'] in added_names:
            skipped['name'] += 1
            continue
        key = (round(lat, 4), round(lot, 4))
        if key in used_coords:
            skipped['coord'] += 1
            continue
        used_names.add(c['name'])
        used_coords.add(key)
        c['latf'], c['lotf'] = lat, lot
        picked.append(c)
    print('선별', len(picked), '개, 제외', skipped)

    def nearest_official(lot, lat):
        return min(official, key=lambda s: (float(s['lot']) - lot) ** 2 + (float(s['lat']) - lat) ** 2)

    today_str = TODAY.strftime('%Y%m%d')
    date_label = f"{TODAY.month}월 {TODAY.day}일({DOW[TODAY.weekday()]})"

    # TideBED는 바다 격자에서만 값을 주므로, 해안 좌표는 실패하면 주변 바다 쪽으로 조금씩 옮겨가며 재시도
    dirs = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    offsets = [(0.0, 0.0)] + [(dy * r, dx * r) for r in (0.004, 0.008, 0.015, 0.025, 0.04) for dy, dx in dirs]

    from collections import Counter
    from concurrent.futures import ThreadPoolExecutor, as_completed
    cache_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '_tidebed_cache.json')
    cache = load(cache_path) if os.path.exists(cache_path) else {}
    hits = Counter()

    def ckey(c):
        return f"{c['name']}|{c['latf']:.5f}|{c['lotf']:.5f}"

    def fetch_point(c):
        order = sorted(range(len(offsets)), key=lambda i: (0 if i == 0 else 1, -hits[i] if i else 0, i))
        for i in order:
            dla, dlo = offsets[i]
            la, lo = c['latf'] + dla, c['lotf'] + dlo
            xml = call(f'{BASE}/tidebed/GetTidebedApiService',
                       {'serviceKey': KEY, 'numOfRows': '30', 'pageNo': '1', 'dataType': 'JSON',
                        'lot': f'{lo:.5f}', 'lat': f'{la:.5f}', 'reqDate': today_str, 'min': '60'}, retries=2)
            items = parse_items(xml)
            if len(items) >= 3:
                hits[i] += 1
                slim = [{k: it.get(k) for k in ('slctdDt', 'slctdHgt', 'obsvtrNm')} for it in items]
                return [slim, f'{la:.5f}', f'{lo:.5f}', i != 0]
        return None

    pending = [c for c in picked if ckey(c) not in cache]
    print(f'조회 대상 {len(pending)}개 (캐시 {len(picked) - len(pending)}개)', flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fetch_point, c): c for c in pending}
        for fu in as_completed(futs):
            cache[ckey(futs[fu])] = fu.result()
            done += 1
            if done % 20 == 0:
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, ensure_ascii=False)
                print(f'  진행 {done}/{len(pending)}', flush=True)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False)
    fetched = [cache[ckey(c)] for c in picked]

    new_entries, fails, moved = [], 0, 0
    copied = 0
    for c, res in zip(picked, fetched):
        if not res:
            # 동해안은 TideBED 격자가 없어 실패 -> 가까운 공식 관측소(55km 이내) 예보를 그대로 사용
            near = nearest_official(c['lotf'], c['latf'])
            dist = ((float(near['lot']) - c['lotf']) ** 2 + (float(near['lat']) - c['latf']) ** 2) ** 0.5
            today_day = next((d for d in near['tideDays'] if d['isToday']), None)
            if dist > 0.5 or not today_day:
                fails += 1
                continue
            slug = make_slug(c['name'])
            if slug in used_slugs:
                slug = make_slug(f"{c['name']}-{c['city']}")
            n, base = 2, slug
            while slug in used_slugs:
                slug = f'{base}-{n}'
                n += 1
            used_slugs.add(slug)
            new_entries.append({
                'slug': slug, 'spotName': c['name'], 'baseName': near['spotName'],
                'baseSlug': near['slug'], 'nearestOfficialName': near['spotName'], 'copyFrom': near['slug'],
                'region': c['region'], 'regionSlug': c['regionSlug'], 'city': c['city'],
                'lot': str(round(c['lotf'], 5)), 'lat': str(round(c['latf'], 5)),
                'todayEvents': today_day['events'], 'dataDateLabel': date_label,
                'kind': c['kind'], 'address': c['address'], 'blurb': c['blurb'],
                'sourceLabel': c['sourceLabel'], 'sourceUrl': c['sourceUrl'],
            })
            copied += 1
            continue
        items, tide_lat, tide_lot, was_moved = res
        series = sorted(items, key=lambda x: x['slctdDt'])
        pts = [(p['slctdDt'][11:16], float(p['slctdHgt'])) for p in series]
        vals = [v for _, v in pts]
        events = []
        for k in range(1, len(pts) - 1):
            is_max = vals[k] >= vals[k - 1] and vals[k] >= vals[k + 1]
            is_min = vals[k] <= vals[k - 1] and vals[k] <= vals[k + 1]
            if is_max and not is_min:
                events.append({'type': 'high', 'typeLabel': '만조', 'time': pts[k][0], 'val': str(round(vals[k]))})
            elif is_min and not is_max:
                events.append({'type': 'low', 'typeLabel': '간조', 'time': pts[k][0], 'val': str(round(vals[k]))})
        if not events:
            fails += 1
            continue
        slug = make_slug(c['name'])
        if slug in used_slugs:
            slug = make_slug(f"{c['name']}-{c['city']}")
        n = 2
        base = slug
        while slug in used_slugs:
            slug = f'{base}-{n}'
            n += 1
        used_slugs.add(slug)
        near = nearest_official(c['lotf'], c['latf'])
        entry = {
            'slug': slug, 'spotName': c['name'], 'baseName': series[0].get('obsvtrNm', near['spotName']),
            'baseSlug': near['slug'], 'nearestOfficialName': near['spotName'],
            'region': c['region'], 'regionSlug': c['regionSlug'], 'city': c['city'],
            'lot': str(round(c['lotf'], 5)), 'lat': str(round(c['latf'], 5)),
            'todayEvents': events, 'todaySeries': [{'time': t, 'val': str(round(v))} for t, v in pts],
            'dataDateLabel': date_label,
            'kind': c['kind'], 'address': c['address'], 'blurb': c['blurb'],
            'sourceLabel': c['sourceLabel'], 'sourceUrl': c['sourceUrl'],
        }
        if was_moved:
            entry['tideLot'], entry['tideLat'] = tide_lot, tide_lat
            moved += 1
        new_entries.append(entry)
    print(f'(바다 쪽으로 좌표 보정한 지점 {moved}개, 인근 관측소 예보 적용 {copied}개)')

    print(f'신규 {len(new_entries)}개 추가, 실패 {fails}개')
    with open(ext_path, 'w', encoding='utf-8') as f:
        json.dump(ext + new_entries, f, ensure_ascii=False, indent=1)
    print('저장 완료: 전체 확장지점', len(ext) + len(new_entries))


if __name__ == '__main__':
    main()
