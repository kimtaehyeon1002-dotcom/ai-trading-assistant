// asset.js — Asset 페이지 렌더링(design/08). 게이트·복호화는 asset-gate.js, 표기 규칙은
// asset-format.js가 담당하고 여기는 복호화된 payload를 카드로 조립하는 것만 한다.
// 카드 구성은 design/08 §3-1 배치표를 따른다: 자산 요약(Hero) · 목표 달성률 · 계좌 4장 ·
// 자산 배분 · 자산 추이 · 통화 노출. 결측 값은 행 자체를 생략한다(빈 문장·₩0 렌더 금지).
// 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var F = global.TAAssetFormat;
  var overlay, form, input, errorEl, content, contentWrap, maskToggle, lockBtn, stopIdle;
  var currentPayload = null;
  var trendRange = 90;

  var ROLE_ORDER = ["kiwoom", "kis_isa", "kis_foreign", "bybit"];  // §4-5 사용 빈도순 고정 배치
  var SERIES = ["var(--chart-series-1)", "var(--chart-series-2)", "var(--chart-series-3)",
                "var(--chart-series-4)", "var(--chart-series-5)"];

  function esc(s) { return F.escapeHtml(s); }

  function orderedAccounts(payload) {
    var byRole = {};
    (payload.accounts || []).forEach(function (a) { byRole[a.role] = a; });
    var ordered = ROLE_ORDER.map(function (r) { return byRole[r]; }).filter(Boolean);
    // 레지스트리에 없는 신규 계좌가 생겨도 화면에서 사라지지 않게 뒤에 붙인다.
    (payload.accounts || []).forEach(function (a) {
      if (ROLE_ORDER.indexOf(a.role) === -1) ordered.push(a);
    });
    return ordered;
  }

  // ── Hero: 자산 요약(§3-2) ──
  function heroHtml(p) {
    var asOf = F.asOf(p.as_of);
    var missing = p.missing_roles || [];
    var rows = "";
    // 총수익·총수익률·투입원금 3열 — 원금을 못 구한 계좌가 섞이면 합계 자체를 생략한다.
    if (p.total_pnl_krw != null) {
      rows = '<div class="v2-stat-row">'
        + '<div class="v2-stat"><span class="v2-stat__label">총수익</span>'
        + '<span class="v2-stat__value--lg v2-updown ' + F.signClass(p.total_pnl_krw) + '">'
        + F.signedAmount(p.total_pnl_krw, "KRW") + "</span></div>"
        + '<div class="v2-stat"><span class="v2-stat__label">총수익률</span>'
        + '<span class="v2-stat__value--lg v2-updown ' + F.signClass(p.total_pnl_pct) + '">'
        + F.pct(p.total_pnl_pct) + "</span></div>"
        + '<div class="v2-stat"><span class="v2-stat__label">투입 원금</span>'
        + '<span class="v2-stat__value--lg">' + F.amount(p.principal_krw, "KRW") + "</span></div>"
        + "</div>";
    }
    return '<div class="v2-card v2-card--hero v2-span-8"' + F.freshnessAttrs(p.as_of) + ">"
      + '<div class="v2-card__header"><h3 class="v2-card__title">자산 요약</h3>'
      + '<span class="v2-card__meta">' + F.freshnessBadges() + " " + esc(asOf) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-stat__value--display v2-freshness-affected">' + F.amount(p.total_assets_krw, "KRW") + "</div>"
      // 전일 대비는 비교 가능한 날에만 존재한다 — 없으면 행 자체를 그리지 않는다(빈 "—" 금지).
      + (p.day_change_pct != null
        ? '<div class="v2-updown ' + F.signClass(p.day_change_pct) + '">' + F.arrow(p.day_change_pct)
          + F.pct(p.day_change_pct) + " 전일 스냅샷 대비"
          + (p.day_change_basis ? ' <span class="v2-card__meta">(' + esc(p.day_change_basis) + " 기준)</span>" : "")
          + "</div>"
        : "")
      + (missing.length
        ? '<span class="v2-partial-note">확보된 ' + (p.covered_roles || []).length + "개 계좌 합계 · "
          + esc(missing.map(roleLabel).join("·")) + " 결측</span>"
        : "")
      + rows
      + sparklineHtml(p.history)
      + "</div></div>";
  }

  function roleLabel(role) {
    var map = { kiwoom: "키움", kis_isa: "한투 ISA", kis_foreign: "한투 위탁", bybit: "BYBIT" };
    return map[role] || role;
  }

  // ── Hero 하단 90일 스파크라인(§3-2) — 단일 계열이므로 기간 손익 방향에 따라 market.* 배정 ──
  function sparklineHtml(history) {
    var pts = (history || []).filter(function (r) { return r.total_assets_krw != null; });
    if (pts.length < 2) return "";
    return chartMount({
      values: pts.map(function (r) { return r.total_assets_krw; }),
      dates: pts.map(function (r) { return r.date; }),
      variant: "spark", color: "direction", format: "krw", maskable: true,
      label: "총자산 최근 추이", height: 56
    }, "margin-top:var(--space-4)");
  }

  /** 차트 마운트 요소 — 실제 SVG는 chart.js가 컨테이너 실측 픽셀로 그린다.
   *  값은 JSON 속성으로만 넘긴다(문자열 조립으로 SVG를 만들면 축·마커에서 좌표가 어긋난다). */
  function chartMount(cfg, style) {
    return '<div class="v2-chart" data-chart="' + esc(JSON.stringify(cfg)) + '"'
      + (style ? ' style="' + style + '"' : "") + "></div>";
  }

  // ── 목표 달성률(§3-3) ──
  function goalHtml(p) {
    if (p.goal_progress_pct == null || p.goal_amount_krw == null) {
      return '<div class="v2-card v2-card--standard v2-span-4">'
        + '<div class="v2-card__header"><h3 class="v2-card__title">목표 달성률</h3></div>'
        + '<div class="v2-card__body"><p class="v2-hub-empty">목표 금액이 설정되지 않았습니다 '
        + "(ASSET_GOAL_KRW).</p></div></div>";
    }
    var remaining = p.goal_amount_krw - (p.total_assets_krw || 0);
    return '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">목표 달성률</h3>'
      + '<span class="v2-card__meta">' + esc(F.asOf(p.as_of)) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-stat__value--display">' + p.goal_progress_pct.toFixed(1) + "%</div>"
      + '<div class="v2-goal-bar"><div class="v2-goal-bar__fill" style="width:'
      + Math.max(0, Math.min(100, p.goal_progress_pct)).toFixed(1) + '%"></div></div>'
      + kv("현재", F.amount(p.total_assets_krw, "KRW"))
      + kv("목표", F.amount(p.goal_amount_krw, "KRW"))
      + kv("남은 금액", F.amount(remaining > 0 ? remaining : 0, "KRW"))
      + goalForecast(p, remaining)
      + "</div></div>";
  }

  /** 차트 위 요약 줄의 한 항목. 값이 이미 마크업(F.amount)일 수 있어 esc는 호출부 책임이다. */
  function legendItem(k, v) {
    return '<span class="v2-chart-legend__item"><span class="v2-chart-legend__k">' + esc(k)
      + '</span><span class="v2-chart-legend__v">' + v + "</span></span>";
  }

  function kv(k, v) {
    return '<div class="v2-kv-row"><span class="v2-kv-row__k">' + esc(k) + '</span>'
      + '<span class="v2-kv-row__v">' + v + "</span></div>";
  }

  /** 달성 예상 시점 — 스냅샷 원장의 실제 월평균 순증에서만 파생한다(추정 없으면 생략). */
  function goalForecast(p, remaining) {
    var hist = (p.history || []).filter(function (r) { return r.total_assets_krw != null; });
    if (hist.length < 2 || remaining <= 0) return "";
    var first = hist[0], last = hist[hist.length - 1];
    var days = (new Date(last.date) - new Date(first.date)) / 86400000;
    if (days < 30) return "";  // 한 달치도 없는 원장으로 미래를 말하지 않는다
    var perMonth = (last.total_assets_krw - first.total_assets_krw) / (days / 30);
    if (perMonth <= 0) return "";
    var months = Math.ceil(remaining / perMonth);
    var eta = new Date();
    eta.setMonth(eta.getMonth() + months);
    return '<div class="v2-insight-dot">월평균 ' + F.money(perMonth, "KRW") + " 순증 유지 시 "
      + eta.getFullYear() + "/" + ("0" + (eta.getMonth() + 1)).slice(-2) + " 달성 예상</div>";
  }

  // ── 계좌 카드(§3-4) ──
  function accountCardHtml(a, asOf) {
    var ccy = a.native_currency;
    // 대표값 위계(§2-4·§3-4): 한투 위탁은 총자산과의 정합을 위해 **원화 환산 합계**가 대표값이고
    // USD 원값은 아래 통화별 웰이 담당한다. BYBIT은 보유 통화($)가 대표값이고 원화는 참고 환산.
    var headlineNative = a.role === "bybit" && a.usd_value != null;
    var headline = headlineNative ? F.amount(a.usd_value, ccy) : F.amount(a.balance_krw, "KRW");
    return '<div class="v2-card v2-card--standard v2-span-4"' + F.freshnessAttrs(asOf) + ">"
      + '<div class="v2-card__header"><h3 class="v2-card__title">' + esc(a.label) + "</h3>"
      + '<span class="v2-card__meta">' + esc(a.sub_label) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-fs-value v2-freshness-affected">' + headline + "</div>"
      + (headlineNative && a.balance_krw != null
        ? '<p class="v2-fs-sub">≈ ' + F.amount(a.balance_krw, "KRW") + "</p>" : "")
      + (a.change_pct != null
        ? '<div class="v2-updown ' + F.signClass(a.change_pct) + '">' + F.arrow(a.change_pct)
          + F.pct(a.change_pct) + " 전일 대비</div>"
        : "")
      + (a.eval_pnl_krw != null
        ? '<p class="v2-body v2-fs-sub">평가손익 <span class="v2-updown ' + F.signClass(a.eval_pnl_krw) + '">'
          + F.signedAmount(a.eval_pnl_krw, "KRW") + " (" + F.pct(a.eval_pnl_pct) + ")</span></p>"
        : "")
      + (a.weight_pct != null ? '<p class="v2-body v2-fs-sub">비중 ' + a.weight_pct.toFixed(1) + "%</p>" : "")
      + (a.balance_krw == null ? '<p class="v2-hub-empty">이 계좌는 이번 수집에서 확보되지 않았습니다.</p>' : "")
      + breakdownHtml(a)
      + currencyWellHtml(a)
      + (a.role === "bybit" ? '<p class="v2-body v2-fs-sub">24시간 시장 · 스냅샷 값</p>' : "")
      + "</div></div>";
  }

  /** 예수금 / 주식 평가액 분해(design/25 §8-3).
   *  계좌 총액이 '현금 얼마 + 주식 얼마'로 이뤄졌는지는 매매 여력 판단의 기본 재료다.
   *  둘 다 결측이면 블록 자체를 렌더하지 않는다(빈 행 금지). 원 통화 계좌는 원 통화로 적는다.
   */
  function breakdownHtml(a) {
    var native = a.native_currency === "USD";
    var sec = native ? a.securities_usd : a.securities_krw;
    var dep = native ? a.deposit_usd : a.deposit_krw;
    var ccy = native ? "USD" : "KRW";
    if (sec == null && dep == null) return "";
    var rows = "";
    if (sec != null) {
      rows += '<div class="v2-breakdown__row"><span class="k">주식 평가액</span>'
        + '<span class="v">' + F.amount(sec, ccy) + "</span></div>";
    }
    if (dep != null) {
      rows += '<div class="v2-breakdown__row"><span class="k">예수금</span>'
        + '<span class="v">' + F.amount(dep, ccy) + "</span></div>";
    }
    return '<div class="v2-breakdown">' + rows + "</div>";
  }

  /** 한투 위탁 듀얼 통화 웰(§2-4) — 원 통화가 1차, 환산은 secondary로 강등.
   *  환율 표기 없는 환산값은 렌더하지 않는다(N1 확장: 환산 근거 필수 병기). */
  function currencyWellHtml(a) {
    if (a.role !== "kis_foreign" || a.usd_value == null) return "";
    var rows = '<div class="v2-ccy-well__row"><span class="v2-ccy-well__label">USD</span>'
      + '<span class="v2-ccy-well__native">' + F.amount(a.usd_value, "USD")
      + (a.balance_krw != null ? '<span class="v2-ccy-well__conv">≈ ' + F.amount(a.balance_krw, "KRW") + "</span>" : "")
      + "</span></div>";
    // 예수금 행은 breakdownHtml이 담당한다(design/25 §8-3) — 여기서 또 그리면 중복이다.
    return '<div class="v2-ccy-well">' + rows + "</div>"
      + (a.fx_rate ? '<p class="v2-body v2-fs-sub">적용 환율 ' + a.fx_rate.toFixed(2) + "원</p>" : "");
  }

  // ── 자산 배분 스택 바(§3-5 = 00 §8-5 AccountAllocationBar) ──
  function allocationHtml(accounts) {
    var withWeight = accounts.filter(function (a) { return a.weight_pct != null; })
      .sort(function (x, y) { return y.weight_pct - x.weight_pct; });  // 비중 큰 순(계약)
    if (!withWeight.length) return "";
    var segs = withWeight.map(function (a, i) {
      // 라벨은 **들어갈 때만** 얹는다 — 잘린 숫자는 없는 것보다 나쁘다(좁은 조각은 범례가 책임진다).
      var label = a.weight_pct >= 12
        ? '<span class="v2-alloc-bar__seglabel">' + a.weight_pct.toFixed(0) + "%</span>" : "";
      return '<div class="v2-alloc-bar__seg" style="width:' + a.weight_pct + "%;background:"
        + SERIES[Math.min(i, SERIES.length - 1)] + '" title="' + esc(a.label) + " " + a.weight_pct.toFixed(1)
        + '%">' + label + "</div>";
    }).join("");
    var legend = withWeight.map(function (a, i) {
      return '<span class="v2-alloc-legend__item"><span class="v2-alloc-legend__chip" style="background:'
        + SERIES[Math.min(i, SERIES.length - 1)] + '"></span>' + esc(a.label)
        + ' <span class="v2-alloc-legend__pct">' + a.weight_pct.toFixed(1) + "%</span></span>";
    }).join("");
    var roles = withWeight.map(function (a) { return esc(a.sub_label); }).join(" / ");
    return '<div class="v2-card v2-card--standard v2-span-8">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">자산 배분</h3>'
      + '<span class="v2-card__meta">계좌별 비중</span></div>'
      + '<div class="v2-card__body"><div class="v2-alloc-bar">' + segs + "</div>"
      + '<div class="v2-alloc-legend">' + legend + "</div>"
      + '<p class="v2-alloc-note">역할: ' + roles + "</p></div></div>";
  }

  // ── 자산 추이(§3-6) ──
  function trendHtml(p) {
    var hist = (p.history || []).filter(function (r) { return r.total_assets_krw != null; });
    var tabs = [30, 90, 180, 365, 0].map(function (d) {
      var label = d === 0 ? "ALL" : d < 365 ? d / 30 + "M" : "1Y";
      return '<button type="button" class="v2-filter-chip" data-trend="' + d + '" aria-pressed="'
        + (d === trendRange ? "true" : "false") + '">' + label + "</button>";
    }).join("");
    var body;
    if (hist.length < 2) {
      // 원장이 하루치뿐인 상태에서 선을 그리면 없는 추세를 보여주게 된다.
      body = '<p class="v2-trend-empty">추이를 그리려면 스냅샷이 2일치 이상 필요합니다 '
        + "(현재 " + hist.length + "일). 데스크톱 자산 동기화를 하루 1회 실행하면 쌓입니다.</p>";
    } else {
      var rows = trendRange ? hist.slice(-trendRange) : hist;
      var values = rows.map(function (r) { return r.total_assets_krw; });
      var refs = p.goal_amount_krw ? [{ value: p.goal_amount_krw, label: "목표" }] : [];
      // 차트 위 요약 줄 — 그림이 말하지 못하는 "얼마나"를 숫자로 못 박는다(design/25 §10과 같은 이유).
      var lo = Math.min.apply(null, values), hi = Math.max.apply(null, values);
      var periodPct = values[0] ? (values[values.length - 1] / values[0] - 1) * 100 : null;
      body = '<div class="v2-chart-legend">'
        + legendItem("구간", esc(rows[0].date) + " → " + esc(rows[rows.length - 1].date) + " (" + rows.length + "일)")
        + (periodPct != null
          ? '<span class="v2-chart-legend__item"><span class="v2-chart-legend__k">구간 등락</span>'
            + '<span class="v2-chart-legend__v v2-updown ' + F.signClass(periodPct) + '">'
            + F.arrow(periodPct) + F.pct(periodPct) + "</span></span>"
          : "")
        + legendItem("최고", F.amount(hi, "KRW"))
        + legendItem("최저", F.amount(lo, "KRW"))
        + (p.goal_amount_krw
          ? '<span class="v2-chart-legend__item"><span class="v2-chart-legend__key v2-chart-legend__key--dash"></span>'
            + '<span class="v2-chart-legend__k">목표</span><span class="v2-chart-legend__v">'
            + F.amount(p.goal_amount_krw, "KRW") + "</span></span>"
          : "")
        + "</div>"
        + chartMount({
          values: values,
          dates: rows.map(function (r) { return r.date; }),
          variant: "full", color: "direction", format: "krw", maskable: true,
          refs: refs, label: "총자산 추이", height: 240
        });
    }
    return '<div class="v2-card v2-card--standard v2-span-8">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">자산 추이</h3>'
      + '<div class="v2-filterbar" data-trend-tabs>' + tabs + "</div></div>"
      + '<div class="v2-card__body">' + body + "</div></div>";
  }

  // ── 통화 노출(§3-7) ──
  function currencyExposureHtml(p) {
    var list = p.currency_exposure || [];
    if (!list.length) return "";
    var rows = list.map(function (e) {
      return '<div class="v2-kv-row"><span class="v2-kv-row__k">' + esc(e.currency) + "</span>"
        + '<span class="v2-kv-row__v">' + F.amount(e.amount_krw, "KRW") + " (" + e.pct.toFixed(1) + "%)</span></div>";
    }).join("");
    return '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">통화 노출</h3></div>'
      + '<div class="v2-card__body">' + rows + fxSensitivity(p) + "</div></div>";
  }

  /** 환율 ±10원 민감도 — 외화 노출과 적용 환율이 모두 있을 때만 계산(파생 추정 = violet 점). */
  function fxSensitivity(p) {
    var fx = null, foreignKrw = 0;
    (p.accounts || []).forEach(function (a) {
      if (a.native_currency === "KRW" || a.balance_krw == null) return;
      if (a.fx_rate) fx = a.fx_rate;
      foreignKrw += a.balance_krw;
    });
    if (!fx || !foreignKrw) return "";
    var delta = foreignKrw / fx * 10;
    return '<div class="v2-insight-dot">환율 ±10원 변동 시 총자산 ±' + F.money(delta, "KRW") + "</div>";
  }

  // ── 렌더 ──
  function render(payload) {
    currentPayload = payload;
    var accounts = orderedAccounts(payload);
    content.innerHTML = heroHtml(payload)
      + goalHtml(payload)
      + accounts.map(function (a) { return accountCardHtml(a, payload.as_of); }).join("")
      + allocationHtml(accounts)
      + trendHtml(payload)
      + currencyExposureHtml(payload);
    contentWrap.hidden = false;
    overlay.hidden = true;
    applyMaskState();
    // 마운트는 마스킹 상태를 확정한 **뒤에** 한다 — 축 라벨이 금액이라, 순서가 바뀌면
    // 가려야 할 값이 한 프레임 동안 그대로 그려진다.
    if (global.TAChart) global.TAChart.initAll(content);
    global.TAAssetGate.paintNavLocks(true);
    if (global.TAFreshness) global.TAFreshness.init(content);
    if (stopIdle) stopIdle();
    stopIdle = global.TAAssetGate.startIdleLock(instantLock);
  }

  function applyMaskState() {
    var masked = global.TAAssetGate.masked();
    content.setAttribute("data-masked", masked ? "1" : "0");
    maskToggle.setAttribute("aria-pressed", masked ? "true" : "false");
    // 차트 y축 눈금·툴팁도 금액이다 — CSS로 가릴 수 없으니(SVG text) 다시 그린다.
    // 이걸 빼면 "금액 가리기"를 켜 놓고도 축에 총자산이 그대로 남는다.
    if (global.TAChart) global.TAChart.refresh(content);
  }

  function toggleMask() {
    global.TAAssetGate.setMasked(!global.TAAssetGate.masked());
    applyMaskState();
  }

  function instantLock() {
    global.TAAssetGate.lock();
    contentWrap.hidden = true;
    content.innerHTML = "";  // 잠근 뒤 DOM에 값이 남지 않게 한다
    overlay.hidden = false;
    global.TAAssetGate.paintNavLocks(false);
    if (stopIdle) { stopIdle(); stopIdle = null; }
    input.value = "";
    input.focus();
  }

  function showError() {
    errorEl.hidden = false;
    input.classList.add("v2-gate-modal__input--error");
    input.value = "";
    input.focus();
  }

  function onSubmit(e) {
    e.preventDefault();
    errorEl.hidden = true;
    input.classList.remove("v2-gate-modal__input--error");
    global.TAAssetGate.unlock(input.value).then(render).catch(showError);
  }

  function init() {
    overlay = doc.getElementById("asset-gate-overlay");
    form = doc.getElementById("asset-gate-form");
    input = doc.getElementById("asset-gate-input");
    errorEl = doc.getElementById("asset-gate-error");
    content = doc.getElementById("asset-content");
    contentWrap = doc.getElementById("asset-content-wrap");
    maskToggle = doc.getElementById("asset-mask-toggle");
    lockBtn = doc.getElementById("asset-lock-btn");
    if (!overlay || !form || !content) return;

    form.addEventListener("submit", onSubmit);
    maskToggle.addEventListener("click", toggleMask);
    lockBtn.addEventListener("click", instantLock);
    global.TAAssetGate.bindModal(overlay, input, null);  // Esc는 되돌아갈 곳이 없어 무동작

    content.addEventListener("click", function (e) {
      var tab = e.target.closest ? e.target.closest("[data-trend]") : null;
      if (!tab || !currentPayload) return;
      trendRange = parseInt(tab.getAttribute("data-trend"), 10);
      render(currentPayload);
    });

    doc.addEventListener("keydown", function (e) {
      if (e.key === "H" && e.shiftKey && !contentWrap.hidden) toggleMask();  // Shift+H(§1-3)
    });

    global.TAAssetGate.tryAutoUnlock().then(function (data) {
      if (data) render(data);
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
