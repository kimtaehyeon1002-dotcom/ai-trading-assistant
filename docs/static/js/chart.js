// chart.js — 공용 차트 엔진(design/00 §2-7·§10-1). 외부 라이브러리 0, 의존 0.
//
// 왜 클라이언트 렌더인가: 서버 SVG는 `preserveAspectRatio="none"`으로 칸에 맞춰 늘려야 해서
// 좌표계가 왜곡된다 — 선은 vector-effect로 버티지만 **점·라벨·격자는 찌그러진다**. 그래서
// 축·눈금·마커·툴팁이 필요한 순간 서버 SVG로는 더 못 간다. 이 모듈은 컨테이너 실측 픽셀로
// 그리므로 원은 원이고 12px 글자는 12px다.
//
// 서버 SVG는 버리지 않는다 — 마운트 요소 안에 폴백으로 남아 있고, 이 모듈이 성공적으로
// 그렸을 때만 치운다(JS 실패 시 최소한 추세선은 보인다).
//
// 마운트 계약:
//   <div class="v2-chart" data-chart='{...json...}'>…폴백 SVG…</div>
// JSON 필드:
//   values   number[]            필수. 결측은 null 허용(선이 끊긴다).
//   dates    string[]            선택. values와 길이 동일해야 x축·툴팁 날짜가 나온다.
//   variant  "spark"|"full"      spark=축 없음(타일용), full=축·격자·라벨(카드용)
//   color    "direction"|"series-1".."series-5"|"flat"
//   unit     "%"|"KRW"|"USD"|…   툴팁·축 라벨 단위
//   format   "krw"|"num"|"pct"   숫자 표기(기본 num)
//   decimals number              num 표기 소수 자릿수(기본 자동)
//   label    string              접근성 라벨·툴팁 제목
//   baseline boolean             구간 첫 값 기준선(spark 기본 true)
//   refs     [{value,label}]     목표선 등 참조선(full)
//   maskable boolean             [data-masked="1"] 안에서 금액을 가린다(Asset 전용)
(function (global) {
  "use strict";

  var doc = global.document;
  var NS = "http://www.w3.org/2000/svg";
  var uid = 0;

  // 축·격자·마커 치수는 한 곳에서만 정한다 — 페이지마다 다른 값을 쓰면 "같은 시스템"으로 안 읽힌다.
  var PAD = {
    full: { top: 10, right: 12, bottom: 20, left: 56 },
    spark: { top: 4, right: 4, bottom: 4, left: 4 }
  };
  var GRID_LINES = 4;

  function reduceMotion() {
    if (doc.documentElement.getAttribute("data-reduce-motion") === "1") return true;
    return !!(global.matchMedia && global.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function el(tag, attrs) {
    var node = doc.createElementNS(NS, tag);
    if (attrs) {
      for (var k in attrs) {
        if (Object.prototype.hasOwnProperty.call(attrs, k) && attrs[k] != null) {
          node.setAttribute(k, attrs[k]);
        }
      }
    }
    return node;
  }

  /** 색은 CSS 변수로만 지정한다(design/22 R6) — 그래서 presentation attribute가 아니라
   *  style 프로퍼티로 넣는다. `stroke="var(--x)"`는 SVG 속성 문법상 해석되지 않는다. */
  function colorVar(cfg, values) {
    if (cfg.color && cfg.color.indexOf("series-") === 0) return "var(--chart-" + cfg.color + ")";
    if (cfg.color === "flat") return "var(--market-flat)";
    var clean = values.filter(function (v) { return v != null; });
    if (clean.length < 2) return "var(--market-flat)";
    var d = clean[clean.length - 1] - clean[0];
    return d > 0 ? "var(--market-up)" : d < 0 ? "var(--market-down)" : "var(--market-flat)";
  }

  // ── 숫자 표기 ──────────────────────────────────────────────────────────────
  function compactKRW(v) {
    var sign = v < 0 ? "-" : "";
    var a = Math.abs(v);
    if (a >= 1e8) return sign + trimZero((a / 1e8).toFixed(a >= 1e9 ? 1 : 2)) + "억";
    if (a >= 1e4) return sign + Math.round(a / 1e4).toLocaleString("ko-KR") + "만";
    return sign + Math.round(a).toLocaleString("ko-KR");
  }

  function trimZero(s) { return s.replace(/\.0+$/, "").replace(/(\.\d*[1-9])0+$/, "$1"); }

  function autoDecimals(span) {
    if (span >= 1000) return 0;
    if (span >= 100) return 1;
    if (span >= 10) return 2;
    if (span >= 1) return 2;
    return 4;
  }

  function fmt(v, cfg, span) {
    if (v == null) return "—";
    if (cfg.format === "krw") return compactKRW(v);
    if (cfg.format === "pct" || cfg.unit === "%") return trimZero(v.toFixed(2)) + "%";
    var d = cfg.decimals != null ? cfg.decimals : autoDecimals(span);
    return v.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
  }

  /** 축 눈금은 반올림된 "깔끔한 수"여야 한다 — 1430.7331 같은 눈금은 읽는 데 시간을 쓰게 한다. */
  function niceStep(rawStep) {
    var exp = Math.floor(Math.log(rawStep) / Math.LN10);
    var pow = Math.pow(10, exp);
    var f = rawStep / pow;
    var nice = f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10;
    return nice * pow;
  }

  function ticks(lo, hi, count) {
    if (!(hi > lo)) return [{ v: lo, step: 1 }];
    var step = niceStep((hi - lo) / count);
    var out = [];
    for (var t = Math.ceil(lo / step) * step; t <= hi + step * 1e-6; t += step) out.push({ v: t, step: step });
    return out;
  }

  /** 눈금 라벨의 소수 자릿수는 **간격**이 정한다 — 값의 정밀도가 아니라. 간격이 1000이면
   *  "6,000.00"은 소수점 두 자리만큼의 잉크를 낭비하고 축을 시끄럽게 한다. */
  function fmtTick(t, cfg) {
    if (cfg.format === "krw") return compactKRW(t.v);
    var d = t.step >= 1 ? 0 : t.step >= 0.1 ? 1 : t.step >= 0.01 ? 2 : 4;
    var s = t.v.toLocaleString("ko-KR", { minimumFractionDigits: d, maximumFractionDigits: d });
    return cfg.unit === "%" || cfg.format === "pct" ? s + "%" : s;
  }

  /** x축을 그릴 수 있는가 — 날짜 배열이 값과 **정확히 같은 길이**일 때만. 길이가 다르면
   *  i번째 점에 i번째 날짜를 붙이는 순간 축이 거짓이 된다. */
  function hasDates(cfg) {
    return !!(cfg.dates && cfg.dates.length === cfg.values.length && cfg.values.length > 1);
  }

  // ── 스케일 ────────────────────────────────────────────────────────────────
  function build(cfg, w, h) {
    var base = PAD[cfg.variant === "full" ? "full" : "spark"];
    // 날짜가 없으면 x축 라벨도 없다 — 그 자리를 비워 두면 차트만 그만큼 납작해진다.
    var pad = {
      top: base.top, right: base.right, left: base.left,
      bottom: hasDates(cfg) ? base.bottom : base.top
    };
    var values = cfg.values;
    var clean = values.filter(function (v) { return v != null; });
    var lo = Math.min.apply(null, clean);
    var hi = Math.max.apply(null, clean);
    // 참조선(목표 등)을 무조건 축에 넣으면 축이 참조선에 끌려간다 — 목표 3억 / 자산 1.8억이면
    // 실제 데이터가 아래 1/4에 눌려 추세를 못 읽는다(실측). 데이터 진폭의 60% 안쪽일 때만
    // 축을 넓히고, 그보다 먼 참조선은 축 밖으로 두고 가장자리에 화살표로 표시한다.
    var reach = (hi - lo) * 0.6 || Math.abs(hi) * 0.1;
    (cfg.refs || []).forEach(function (r) {
      if (r.value == null) return;
      if (r.value < lo && r.value >= lo - reach) lo = r.value;
      else if (r.value > hi && r.value <= hi + reach) hi = r.value;
    });
    // 값이 한 점에 몰려도 선이 테두리에 눌러붙지 않게 여유를 준다.
    if (hi === lo) { hi += Math.abs(hi || 1) * 0.01; lo -= Math.abs(lo || 1) * 0.01; }
    var headroom = (hi - lo) * (cfg.variant === "full" ? 0.12 : 0.16);
    lo -= headroom; hi += headroom;

    var innerW = Math.max(1, w - pad.left - pad.right);
    var innerH = Math.max(1, h - pad.top - pad.bottom);
    var step = values.length > 1 ? innerW / (values.length - 1) : 0;
    return {
      pad: pad, lo: lo, hi: hi, innerW: innerW, innerH: innerH,
      x: function (i) { return pad.left + i * step; },
      y: function (v) { return pad.top + (1 - (v - lo) / (hi - lo)) * innerH; }
    };
  }

  function pathOf(values, s) {
    var d = "", pen = false;
    for (var i = 0; i < values.length; i++) {
      if (values[i] == null) { pen = false; continue; }
      d += (pen ? "L" : "M") + s.x(i).toFixed(1) + " " + s.y(values[i]).toFixed(1) + " ";
      pen = true;
    }
    return d.trim();
  }

  function areaOf(values, s, floorY) {
    var segs = [], cur = null;
    for (var i = 0; i < values.length; i++) {
      if (values[i] == null) { cur = null; continue; }
      if (!cur) { cur = []; segs.push(cur); }
      cur.push([s.x(i), s.y(values[i])]);
    }
    return segs.filter(function (g) { return g.length > 1; }).map(function (g) {
      var d = "M" + g[0][0].toFixed(1) + " " + floorY.toFixed(1);
      g.forEach(function (p) { d += "L" + p[0].toFixed(1) + " " + p[1].toFixed(1); });
      return d + "L" + g[g.length - 1][0].toFixed(1) + " " + floorY.toFixed(1) + "Z";
    }).join(" ");
  }

  // ── 렌더 ──────────────────────────────────────────────────────────────────
  function render(host) {
    var cfg = host.__chart;
    if (!cfg) return;
    var w = host.clientWidth;
    if (!w) return;                       // 아직 레이아웃 전(hidden 등) — ResizeObserver가 다시 부른다
    var h = cfg.height || (cfg.variant === "full" ? 220 : 56);
    var full = cfg.variant === "full";

    var s = build(cfg, w, h);
    var color = colorVar(cfg, cfg.values);
    var gid = "tachart-" + (++uid);
    var masked = !!(cfg.maskable && host.closest && host.closest('[data-masked="1"]'));
    var span = s.hi - s.lo;

    var svg = el("svg", {
      class: "v2-chart__svg", width: w, height: h, viewBox: "0 0 " + w + " " + h,
      role: "img", "aria-label": cfg.label || "추이 차트"
    });

    var defs = el("defs");
    var grad = el("linearGradient", { id: gid, x1: "0", y1: "0", x2: "0", y2: "1" });
    // 면 채우기는 계열색 10% → 0%의 소프트 그라디언트다. 불투명한 블록으로 채우면
    // 면이 선보다 무거워져 추세선이 면 위에 얹힌 장식처럼 읽힌다 — 면은 방향을 거들 뿐이다.
    var s0 = el("stop", { offset: "0", "stop-opacity": full ? "0.10" : "0.12" });
    var s1 = el("stop", { offset: "1", "stop-opacity": "0" });
    s0.style.stopColor = color; s1.style.stopColor = color;
    grad.appendChild(s0); grad.appendChild(s1);
    defs.appendChild(grad);
    svg.appendChild(defs);

    // ① 격자 + y 눈금(full 전용) — 데이터보다 뒤, 항상 1px 실선(design/00 §9-2 '격자는 물러선다')
    if (full) {
      var g = el("g", { class: "v2-chart__grid" });
      ticks(s.lo + span * 0.06, s.hi - span * 0.06, GRID_LINES).forEach(function (t) {
        var y = s.y(t.v);
        g.appendChild(el("line", {
          class: "v2-chart__gridline", x1: s.pad.left, y1: y.toFixed(1),
          x2: s.pad.left + s.innerW, y2: y.toFixed(1)
        }));
        var lab = el("text", { class: "v2-chart__ytick", x: s.pad.left - 8, y: (y + 4).toFixed(1) });
        lab.textContent = masked ? "••••" : fmtTick(t, cfg);
        g.appendChild(lab);
      });
      svg.appendChild(g);
    }

    // ② 면적 → ③ 기준선/참조선 → ④ 선 순서. 선이 항상 위에 와야 값이 가려지지 않는다.
    var floorY = s.pad.top + s.innerH;
    var baseVal = null;
    if (cfg.baseline !== false && !full) {
      var first = cfg.values.filter(function (v) { return v != null; })[0];
      if (first != null) { baseVal = first; floorY = s.y(first); }
    }
    var area = el("path", { class: "v2-chart__area", d: areaOf(cfg.values, s, floorY), fill: "url(#" + gid + ")" });
    svg.appendChild(area);

    if (baseVal != null) {
      svg.appendChild(el("line", {
        class: "v2-chart__baseline", x1: s.pad.left, y1: floorY.toFixed(1),
        x2: s.pad.left + s.innerW, y2: floorY.toFixed(1)
      }));
    }

    (cfg.refs || []).forEach(function (r) {
      if (r.value == null) return;
      var y = s.y(r.value);
      var top = s.pad.top, bot = s.pad.top + s.innerH;
      var offUp = y < top, offDown = y > bot;
      var drawY = offUp ? top : offDown ? bot : y;
      svg.appendChild(el("line", {
        class: "v2-chart__ref" + (offUp || offDown ? " v2-chart__ref--off" : ""),
        x1: s.pad.left, y1: drawY.toFixed(1), x2: s.pad.left + s.innerW, y2: drawY.toFixed(1)
      }));
      if (r.label && full) {
        var rl = el("text", {
          class: "v2-chart__reflabel", x: s.pad.left + s.innerW,
          y: (offUp ? drawY + 13 : drawY - 6).toFixed(1), "text-anchor": "end"
        });
        // 축 밖 참조선은 화살표로 "이 방향으로 더 멀리 있다"를 말해 준다 — 가장자리에 그은
        // 선을 실제 값 위치로 오독하면 거짓말이 된다.
        rl.textContent = r.label + (offUp ? " ↑" : offDown ? " ↓" : "");
        svg.appendChild(rl);
      }
    });

    var line = el("path", { class: "v2-chart__line", d: pathOf(cfg.values, s), fill: "none" });
    line.style.stroke = color;
    svg.appendChild(line);

    // ⑤ 마커 — 끝점은 항상, 고·저점은 full에서만(작은 타일에 3개 점은 소음이다).
    var idx = [];
    for (var i = 0; i < cfg.values.length; i++) if (cfg.values[i] != null) idx.push(i);
    if (idx.length) {
      var last = idx[idx.length - 1];
      if (full) {
        var hiI = idx[0], loI = idx[0];
        idx.forEach(function (i2) {
          if (cfg.values[i2] > cfg.values[hiI]) hiI = i2;
          if (cfg.values[i2] < cfg.values[loI]) loI = i2;
        });
        [[hiI, "최고"], [loI, "최저"]].forEach(function (pair) {
          var i3 = pair[0];
          if (i3 === last) return;
          var m = el("circle", {
            class: "v2-chart__extreme", cx: s.x(i3).toFixed(1), cy: s.y(cfg.values[i3]).toFixed(1), r: 3.5
          });
          m.style.fill = color;
          svg.appendChild(m);
          if (!masked) {
            var t2 = el("text", {
              class: "v2-chart__extremelabel",
              x: s.x(i3).toFixed(1),
              y: (s.y(cfg.values[i3]) + (pair[1] === "최고" ? -9 : 15)).toFixed(1),
              "text-anchor": s.x(i3) > s.pad.left + s.innerW * 0.85 ? "end"
                : s.x(i3) < s.pad.left + s.innerW * 0.15 ? "start" : "middle"
            });
            t2.textContent = fmt(cfg.values[i3], cfg, span);
            svg.appendChild(t2);
          }
        });
      }
      // 라이브 펄스 — 끝점에서 퍼지는 고리. **켜는 조건은 CSS가 쥔다**: 조상에
      // [data-live="on"]이 있을 때만 애니메이션이 돈다(design/00 §9-2 S2 — 유효 세션·FRESH
      // 밖에서 라이브처럼 보이는 스타일은 금지다. 실제 오독 사고에서 나온 규칙이다).
      // 마크업은 항상 두고 상태만 CSS로 가르는 이유는, 켜고 끌 때 DOM을 다시 만들지 않기 위함이다.
      var pulse = el("circle", {
        class: "v2-chart__pulse", cx: s.x(last).toFixed(1), cy: s.y(cfg.values[last]).toFixed(1),
        r: full ? 5.5 : 4.5
      });
      pulse.style.stroke = color;
      svg.appendChild(pulse);

      // 끝점: 표면색 2px 링을 둘러 선·격자와 겹쳐도 읽힌다(dataviz surface ring).
      var ring = el("circle", {
        class: "v2-chart__endring", cx: s.x(last).toFixed(1), cy: s.y(cfg.values[last]).toFixed(1),
        r: full ? 5.5 : 4.5
      });
      var dot = el("circle", {
        class: "v2-chart__end", cx: s.x(last).toFixed(1), cy: s.y(cfg.values[last]).toFixed(1),
        r: full ? 3.5 : 2.8
      });
      dot.style.fill = color;
      svg.appendChild(ring); svg.appendChild(dot);
    }

    // ⑥ x축 날짜(full) — 라벨은 4~5개면 충분하다. 더 넣으면 서로 부딪힌다.
    if (full && hasDates(cfg)) {
      var want = Math.max(2, Math.min(5, Math.floor(s.innerW / 90)));
      var gx = el("g", { class: "v2-chart__xaxis" });
      for (var k = 0; k < want; k++) {
        var di = Math.round(k * (cfg.values.length - 1) / (want - 1));
        var tx = el("text", {
          class: "v2-chart__xtick", x: s.x(di).toFixed(1), y: h - 4,
          "text-anchor": k === 0 ? "start" : k === want - 1 ? "end" : "middle"
        });
        tx.textContent = shortDate(cfg.dates[di]);
        gx.appendChild(tx);
      }
      svg.appendChild(gx);
    }

    // ⑦ 커서 레이어(hover/focus) — 크로스헤어가 x를 잡아 준다. 2px 선을 겨냥할 필요가 없다.
    var cursor = el("g", { class: "v2-chart__cursor" });
    var cline = el("line", { class: "v2-chart__crosshair", y1: s.pad.top, y2: s.pad.top + s.innerH });
    var cdotRing = el("circle", { class: "v2-chart__cursorring", r: full ? 6 : 5 });
    var cdot = el("circle", { class: "v2-chart__cursordot", r: full ? 4 : 3.2 });
    cdot.style.fill = color;
    cursor.appendChild(cline); cursor.appendChild(cdotRing); cursor.appendChild(cdot);
    svg.appendChild(cursor);

    // 등장 애니메이션: 300ms 1회(design/00 §10-1). 리사이즈 재렌더에서는 생략한다 —
    // 창을 줄일 때마다 차트가 다시 그려지는 것은 애니메이션이 아니라 깜빡임이다.
    if (!host.__drawn && !reduceMotion()) {
      var len = line.getTotalLength ? line.getTotalLength() : 0;
      if (len) {
        line.style.strokeDasharray = len + " " + len;
        line.style.strokeDashoffset = len;
        line.style.transition = "stroke-dashoffset 300ms var(--motion-easing)";
        area.style.opacity = "0";
        area.style.transition = "opacity 300ms var(--motion-easing)";
        global.requestAnimationFrame(function () {
          global.requestAnimationFrame(function () {
            line.style.strokeDashoffset = "0";
            area.style.opacity = "1";
          });
        });
      }
    }
    host.__drawn = true;

    host.textContent = "";                 // 서버 폴백 SVG 제거 — 이제 우리가 그린다
    host.appendChild(svg);

    var tip = doc.createElement("div");
    tip.className = "v2-chart__tip";
    tip.hidden = true;
    host.appendChild(tip);

    host.__hit = {
      s: s, cfg: cfg, cursor: cursor, cline: cline, cdot: cdot, cdotRing: cdotRing,
      tip: tip, masked: masked, span: span, w: w, h: h
    };
    bindHover(host);
  }

  function shortDate(d) {
    if (!d) return "";
    var m = String(d).match(/(\d{4})-(\d{2})-(\d{2})/);
    return m ? m[2] + "/" + m[3] : String(d).slice(0, 5);
  }

  function nearestIndex(host, clientX) {
    var st = host.__hit, s = st.s, n = st.cfg.values.length;
    var rect = host.getBoundingClientRect();
    var x = clientX - rect.left;
    if (n < 2) return 0;
    var step = s.innerW / (n - 1);
    var i = Math.round((x - s.pad.left) / step);
    return Math.max(0, Math.min(n - 1, i));
  }

  function showAt(host, i) {
    var st = host.__hit, cfg = st.cfg, s = st.s;
    var v = cfg.values[i];
    if (v == null) return;
    var cx = s.x(i), cy = s.y(v);
    st.cline.setAttribute("x1", cx.toFixed(1));
    st.cline.setAttribute("x2", cx.toFixed(1));
    [st.cdot, st.cdotRing].forEach(function (c) {
      c.setAttribute("cx", cx.toFixed(1)); c.setAttribute("cy", cy.toFixed(1));
    });
    st.cursor.classList.add("is-on");

    // 값이 먼저, 라벨이 뒤(dataviz: 읽는 사람은 이미 계열을 안다 — 숫자를 원한다).
    st.tip.textContent = "";
    var head = doc.createElement("div");
    head.className = "v2-chart__tip-v";
    head.textContent = st.masked ? "••••" : fmt(v, cfg, st.span);
    st.tip.appendChild(head);

    var first = cfg.values.filter(function (x2) { return x2 != null; })[0];
    if (first) {
      var delta = (v / first - 1) * 100;
      var sub = doc.createElement("div");
      sub.className = "v2-chart__tip-d " + (delta > 0 ? "up" : delta < 0 ? "down" : "");
      sub.textContent = (delta > 0 ? "▲ +" : delta < 0 ? "▼ " : "− ") + trimZero(delta.toFixed(2)) + "% 구간 시작 대비";
      st.tip.appendChild(sub);
    }
    if (hasDates(cfg) && cfg.dates[i]) {
      var dt = doc.createElement("div");
      dt.className = "v2-chart__tip-k";
      dt.textContent = cfg.dates[i];
      st.tip.appendChild(dt);
    }
    st.tip.hidden = false;

    // 가로는 카드 밖으로 나가면 잘리므로 가둔다. 세로는 반대로 **가두면 안 된다** —
    // 56px 타일 안에 40px 툴팁을 욱여넣으면 툴팁이 차트를 통째로 덮는다(실측). 위로 넘치게
    // 두고 hover 시 타일을 z축으로 올려 이웃 타일에 가리지 않게 한다(components.css).
    var tw = st.tip.offsetWidth;
    st.tip.style.left = Math.max(2, Math.min(st.w - tw - 2, cx - tw / 2)).toFixed(1) + "px";
    st.tip.style.top = (cy - st.tip.offsetHeight - 12).toFixed(1) + "px";
    host.__i = i;
  }

  function hide(host) {
    if (!host.__hit) return;
    host.__hit.cursor.classList.remove("is-on");
    host.__hit.tip.hidden = true;
  }

  function bindHover(host) {
    if (host.__bound) return;
    host.__bound = true;
    host.addEventListener("pointermove", function (e) { showAt(host, nearestIndex(host, e.clientX)); });
    host.addEventListener("pointerleave", function () { hide(host); });
    host.addEventListener("blur", function () { hide(host); });
    // 키보드도 같은 정보를 준다(dataviz: 포커스와 호버는 동일 상세도).
    host.addEventListener("keydown", function (e) {
      var n = host.__hit.cfg.values.length;
      var i = host.__i == null ? n - 1 : host.__i;
      if (e.key === "ArrowRight") i = Math.min(n - 1, i + 1);
      else if (e.key === "ArrowLeft") i = Math.max(0, i - 1);
      else if (e.key === "Home") i = 0;
      else if (e.key === "End") i = n - 1;
      else if (e.key === "Escape") { hide(host); return; }
      else return;
      e.preventDefault();
      showAt(host, i);
    });
  }

  // ── 마운트 ────────────────────────────────────────────────────────────────
  function mount(host) {
    var raw = host.getAttribute("data-chart");
    if (!raw) return;
    var cfg;
    try { cfg = JSON.parse(raw); } catch (err) { return; }
    var vals = (cfg.values || []).filter(function (v) { return v != null; });
    if (vals.length < 2) return;           // 점 1개로 선을 그리면 없는 추세를 보여주게 된다
    host.__chart = cfg;
    host.__drawn = false;
    if (host.tabIndex < 0) host.tabIndex = 0;
    host.classList.add("v2-chart--live");
    render(host);
    if (global.ResizeObserver && !host.__ro) {
      var t = null;
      host.__ro = new global.ResizeObserver(function () {
        global.clearTimeout(t);
        t = global.setTimeout(function () { resize(host); }, 80);
      });
      host.__ro.observe(host);
    }
    // 첫 렌더가 **레이아웃 확정 전**에 걸릴 수 있다 — 스타일시트가 아직 안 붙었으면
    // clientWidth가 엉뚱한 값(실측 126px)이고, 그 폭으로 잡은 좌표계가 그대로 굳는다.
    // 그러면 x축 라벨이 2개만 나오고 호버가 항상 마지막 점으로 튄다(실측). 레이아웃이
    // 안정되는 세 시점에서 폭을 다시 재고, 달라졌을 때만 다시 그린다.
    settle(host);
  }

  function resize(host) {
    hide(host);
    render(host);
  }

  /** 폭이 바뀌었을 때만 재렌더 — 같은 폭이면 아무 일도 하지 않아 애니메이션이 재생되지 않는다. */
  function remeasure(host) {
    if (host.__hit && host.clientWidth && host.clientWidth !== host.__hit.w) resize(host);
  }

  function settle(host) {
    global.requestAnimationFrame(function () { remeasure(host); });
    if (doc.readyState !== "complete") {
      global.addEventListener("load", function () { remeasure(host); }, { once: true });
    }
    if (doc.fonts && doc.fonts.ready && doc.fonts.ready.then) {
      doc.fonts.ready.then(function () { remeasure(host); });
    }
    // 백그라운드 탭에서 열린 경우 — rAF가 스로틀돼 위 세 시점이 전부 헛돈다(실측: 배경 탭에서
    // 폭 불일치). 탭이 실제로 보이는 순간 한 번 더 재는 것이 유일하게 믿을 수 있는 지점이다.
    if (!host.__vis) {
      host.__vis = function () { if (doc.visibilityState === "visible") remeasure(host); };
      doc.addEventListener("visibilitychange", host.__vis);
    }
  }

  function initAll(root) {
    var scope = root || doc;
    var nodes = scope.querySelectorAll ? scope.querySelectorAll("[data-chart]") : [];
    Array.prototype.forEach.call(nodes, mount);
  }

  /** 이미 마운트된 차트를 다시 그린다(마스킹 토글처럼 값 표기 규칙만 바뀔 때). */
  function refresh(root) {
    var scope = root || doc;
    Array.prototype.forEach.call(scope.querySelectorAll("[data-chart]"), function (host) {
      if (host.__chart) { hide(host); render(host); }
    });
  }

  /** 새 데이터로 갈아끼운다(라이브 폴링). 등장 애니메이션은 재생하지 않는다 —
   *  값이 갱신될 때마다 선이 다시 그려지면 그건 갱신이 아니라 깜빡임이다. */
  function setData(host, values, dates) {
    if (!host || !host.__chart || !values || values.length < 2) return false;
    host.__chart.values = values;
    host.__chart.dates = dates || host.__chart.dates;
    hide(host);
    render(host);
    return true;
  }

  global.TAChart = { initAll: initAll, refresh: refresh, mount: mount, setData: setData };

  if (doc.readyState === "loading") {
    doc.addEventListener("DOMContentLoaded", function () { initAll(doc); });
  } else {
    initAll(doc);
  }
})(window);
