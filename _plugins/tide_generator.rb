require 'json'

module Jekyll
  class TideGenerator < Generator
    safe true
    priority :normal

    def generate(site)
      spots = site.data['tide_spots']
      return unless spots&.any?

      Jekyll.logger.info "TideGenerator:", "#{spots.size}개 물때표 페이지 생성 중..."

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

      by_region = spots.group_by { |s| s['regionSlug'] }
      by_region.each do |region_slug, region_spots|
        region_name = region_spots.first['region']
        site.pages << RegionPage.new(site, region_name, region_slug, region_spots)
      end

      Jekyll.logger.info "TideGenerator:", "완료 (#{spots.size}개 지점, #{by_region.size}개 지역)"
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
      self.data['same_region'] = same_region
      self.data['nearby_suggestions'] = nearby

      today = spot['tideDays'].find { |d| d['isToday'] } || spot['tideDays'].first
      self.data['todayTides'] = today['events']
      self.data['todayMulddae'] = "#{today['mulddae']}물"
      vals = today['events'].map { |e| e['val'].to_f }
      self.data['todayRange'] = (vals.max - vals.min).round rescue 0

      self.data['chartSvg'] = build_chart_svg(today['events'])

      self.data['title'] = "#{spot['spotName']} 물때표 - 오늘 만조·간조 시각 | 우아물때"
      self.data['description'] = "#{spot['spotName']}(#{spot['region']} #{spot['city']}) 오늘의 물때표. 만조·간조 시각과 조위를 국립해양조사원 공식 데이터로 확인하세요."
    end

    def build_chart_svg(events)
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
