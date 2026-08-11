require 'json'

module Jekyll
  module TideChart
    def self.build_svg(events)
      return '' if events.size < 2
      pts = events.map { |e|
        h, m = e['time'].split(':').map(&:to_i)
        [h * 60 + m, e['val'].to_f]
      }.sort_by { |t, _| t }

      steps = 60
      t0, t1 = pts.first[0], pts.last[0]
      return '' if t1 <= t0

      curve = []
      (0..steps).each do |i|
        t = t0 + (t1 - t0) * i / steps.to_f
        seg = pts.each_cons(2).find { |a, b| t >= a[0] && t <= b[0] } || [pts[0], pts[1]]
        (ta, va), (tb, vb) = seg
        frac = tb > ta ? (t - ta) / (tb - ta).to_f : 0
        smooth = (1 - Math.cos(frac * Math::PI)) / 2.0
        v = va + (vb - va) * smooth
        curve << [t, v]
      end

      vmin = curve.map { |_, v| v }.min
      vmax = curve.map { |_, v| v }.max
      w, h, pad = 720, 220, 30
      x = ->(i) { pad + (w - 2 * pad) * i / steps.to_f }
      y = ->(v) { vmax > vmin ? (h - pad - (h - 2 * pad) * (v - vmin) / (vmax - vmin)) : h / 2.0 }

      points = curve.each_with_index.map { |(_, v), i| "#{x.call(i).round(1)},#{y.call(v).round(1)}" }.join(' ')
      area = "#{pad},#{h - pad} #{points} #{(w - pad)},#{h - pad}"

      labels = []
      pts.each do |t, v|
        frac_i = (t - t0) / (t1 - t0).to_f * steps
        hh = t / 60
        mm = t % 60
        labels << %(<text x="#{x.call(frac_i).round(1)}" y="#{h - 8}" font-size="11" fill="#64748B" text-anchor="middle">#{format('%02d:%02d', hh, mm)}</text>)
      end

      <<~SVG
        <svg viewBox="0 0 #{w} #{h}" xmlns="http://www.w3.org/2000/svg">
          <polygon points="#{area}" fill="#0891B2" opacity="0.12"/>
          <polyline points="#{points}" fill="none" stroke="#0891B2" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
          #{labels.join("\n  ")}
        </svg>
      SVG
    end

    # 시계열(24포인트)에서 직접 부드러운 곡선 SVG 생성 (확장지점용)
    def self.build_svg_from_series(series)
      return '' if series.size < 2
      pts = series.map { |p|
        h, m = p['time'].split(':').map(&:to_i)
        [h * 60 + m, p['val'].to_f]
      }.sort_by { |t, _| t }

      vmin = pts.map { |_, v| v }.min
      vmax = pts.map { |_, v| v }.max
      w, h, pad = 720, 220, 30
      t0, t1 = pts.first[0], pts.last[0]
      x = ->(t) { pad + (w - 2 * pad) * (t - t0) / (t1 - t0).to_f }
      y = ->(v) { vmax > vmin ? (h - pad - (h - 2 * pad) * (v - vmin) / (vmax - vmin)) : h / 2.0 }

      points = pts.map { |t, v| "#{x.call(t).round(1)},#{y.call(v).round(1)}" }.join(' ')
      area = "#{pad},#{h - pad} #{points} #{(w - pad)},#{h - pad}"

      labels = []
      pts.each_with_index do |(t, _), i|
        next unless i.even?
        hh = t / 60
        labels << %(<text x="#{x.call(t).round(1)}" y="#{h - 8}" font-size="11" fill="#64748B" text-anchor="middle">#{format('%02d:00', hh)}</text>)
      end

      <<~SVG
        <svg viewBox="0 0 #{w} #{h}" xmlns="http://www.w3.org/2000/svg">
          <polygon points="#{area}" fill="#0891B2" opacity="0.12"/>
          <polyline points="#{points}" fill="none" stroke="#0891B2" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>
          #{labels.join("\n  ")}
        </svg>
      SVG
    end
  end

  class TideGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      spots = site.data['tide_spots'] || []
      extended = site.data['extended_spots'] || []
      return unless spots.any? || extended.any?

      Jekyll.logger.info "TideGenerator:", "#{spots.size}개 공식 + #{extended.size}개 확장지점 생성 중..."

      spots.each do |spot|
        same_region = spots
          .select { |s| s['regionSlug'] == spot['regionSlug'] && s['slug'] != spot['slug'] }
          .first(8)
          .map { |s| { 'slug' => s['slug'], 'name' => s['spotName'] } }

        nearby = spots
          .select { |s| s['slug'] != spot['slug'] }
          .sample(3)
          .map { |s| { 'slug' => s['slug'], 'name' => s['spotName'] } }

        site.pages << SpotPage.new(site, spot, same_region, nearby)
      end

      extended.each do |spot|
        same_region = (spots + extended)
          .select { |s| s['regionSlug'] == spot['regionSlug'] && s['slug'] != spot['slug'] }
          .first(8)
          .map { |s| { 'slug' => s['slug'], 'name' => s['spotName'] } }

        nearby = extended
          .select { |s| s['slug'] != spot['slug'] }
          .sample(3)
          .map { |s| { 'slug' => s['slug'], 'name' => s['spotName'] } }

        site.pages << ExtendedSpotPage.new(site, spot, same_region, nearby)
      end

      all_light = spots.map { |s| s.merge('isInterpolated' => false) } +
                  extended.map { |s| s.merge('isInterpolated' => true) }

      by_region = all_light.group_by { |s| s['regionSlug'] }
      by_region.each do |region_slug, region_spots|
        region_name = region_spots.first['region']
        site.pages << RegionPage.new(site, region_name, region_slug, region_spots)
      end

      Jekyll.logger.info "TideGenerator:", "완료 (총 #{spots.size + extended.size}개 지점, #{by_region.size}개 지역)"
    end
  end

  class SpotPage < Page
    def initialize(site, spot, same_region, nearby)
      @site = site
      @base = site.source
      @dir  = "spot/#{spot['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'spot.html')
      self.data.merge!(spot)
      self.data['layout'] = 'spot'
      self.data['isInterpolated'] = false
      self.data['same_region'] = same_region
      self.data['nearby_suggestions'] = nearby

      today = spot['tideDays'].find { |d| d['isToday'] } || spot['tideDays'].first
      self.data['todayTides'] = today['events']
      self.data['todayMulddae'] = "#{today['mulddae']}물"
      vals = today['events'].map { |e| e['val'].to_f }
      self.data['todayRange'] = (vals.max - vals.min).round rescue 0

      self.data['chartSvg'] = TideChart.build_svg(today['events'])

      self.data['title'] = "#{spot['spotName']} 물때표 - 오늘 만조·간조 시각 | 우아물때"
      self.data['description'] = "#{spot['spotName']}(#{spot['region']} #{spot['city']}) 오늘의 물때표. 만조·간조 시각과 조위를 국립해양조사원 공식 데이터로 확인하세요."
    end
  end

  class ExtendedSpotPage < Page
    def initialize(site, spot, same_region, nearby)
      @site = site
      @base = site.source
      @dir  = "spot/#{spot['slug']}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'spot.html')
      self.data.merge!(spot)
      self.data['layout'] = 'spot'
      self.data['isInterpolated'] = true
      self.data['same_region'] = same_region
      self.data['nearby_suggestions'] = nearby

      self.data['todayTides'] = spot['todayEvents']
      vals = spot['todayEvents'].map { |e| e['val'].to_f }
      self.data['todayRange'] = (vals.max - vals.min).round rescue 0
      self.data['todayMulddae'] = '추정'

      self.data['chartSvg'] = TideChart.build_svg_from_series(spot['todaySeries'])

      self.data['title'] = "#{spot['spotName']} 물때표 - 오늘 만조·간조 추정 시각 | 우아물때"
      self.data['description'] = "#{spot['spotName']}(#{spot['region']} #{spot['city']}) 오늘의 물때 추정치. 인근 기준항 #{spot['baseName']} 데이터를 보정하여 계산했습니다."
    end
  end

  class RegionPage < Page
    def initialize(site, region, region_slug, spots)
      @site = site
      @base = site.source
      @dir  = "region/#{region_slug}"
      @name = 'index.html'

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'region.html')
      self.data['layout'] = 'region'
      self.data['region'] = region
      self.data['regionSlug'] = region_slug
      self.data['spots'] = spots
      self.data['title'] = "#{region} 물때표 총정리 | 우아물때 #{spots.size}개 지점"
      self.data['description'] = "#{region} 물때표 #{spots.size}개 지점 총정리. 만조·간조 시각을 국립해양조사원 공식 데이터로 확인하세요."
    end
  end
end
