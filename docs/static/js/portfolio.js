// portfolio.js — Portfolio 종목 단면(design/09). Asset과 같은 암호문(assets.enc.json)·같은
// 게이트 세션(asset-gate.js)을 쓴다 — Asset에서 이미 해제했다면 tryAutoUnlock()만으로 바로 열린다.
// 구성(design/09 §1-1): Hero 종합 → 계좌 탭 → Compact 4카드 → 보유종목 테이블 + 비중 구성 →
// 종목 상세 패널(우측 드로어). Asset이 시간축이라면 여기는 "지금 무엇을 들고 있나"의 단면이다.
// 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var F = global.TAAssetFormat;
  var overlay, form, input, errorEl, contentWrap, tabsEl, contentEl, heroEl, maskToggle, lockBtn, panelSlot;
  var payload = null;
  var accounts = [];
  var activeRole = null;
  var stopIdle = null;

  var ROLE_ORDER = ["kiwoom", "kis_isa", "kis_foreign", "bybit"];
  var SERIES = ["var(--chart-series-1)", "var(--chart-series-2)", "var(--chart-series-3)",
                "var(--chart-series-4)"];
  var OTHERS = "var(--chart-series-5)";

  function esc(s) { return F.escapeHtml(s); }

  function accountCurrency(a) { return a.native_currency || "KRW"; }

  /** 보유종목 행의 평가금액 — 계좌 통화 기준(§3-3: 한 행 안에서 단위를 섞지 않는다). */
  function holdingValue(h) {
    return h.value_krw != null ? h.value_krw : h.value_usd;
  }

  function ordered(list) {
    var byRole = {};
    list.forEach(function (a) { byRole[a.role] = a; });
    var out = ROLE_ORDER.map(function (r) { return byRole[r]; }).filter(Boolean);
    list.forEach(function (a) { if (ROLE_ORDER.indexOf(a.role) === -1) out.push(a); });
    return out;
  }

  function activeAccount() {
    return accounts.filter(function (a) { return a.role === activeRole; })[0] || null;
  }

  // ── Hero: 포트폴리오 종합(§3-1) ──
  function heroHtml() {
    var rows = accounts.map(function (a) {
      return '<div class="v2-kv-row" data-goto="' + esc(a.role) + '" style="cursor:pointer">'
        + '<span class="v2-kv-row__k">' + esc(a.label) + " · " + esc(a.sub_label) + "</span>"
        + '<span class="v2-kv-row__v">' + F.amount(a.balance_krw, "KRW")
        + (a.change_pct != null
          ? ' <span class="v2-updown ' + F.signClass(a.change_pct) + '">' + F.arrow(a.change_pct)
            + F.pct(a.change_pct) + "</span>" : "")
        + (a.weight_pct != null ? " · " + a.weight_pct.toFixed(1) + "%" : "")
        + "</span></div>";
    }).join("");
    var fx = (accounts.filter(function (a) { return a.fx_rate; })[0] || {}).fx_rate;
    return '<div class="v2-card v2-card--hero v2-span-12"' + F.freshnessAttrs(payload.as_of) + ">"
      + '<div class="v2-card__header"><h3 class="v2-card__title">포트폴리오 종합</h3>'
      + '<span class="v2-card__meta">' + F.freshnessBadges() + " " + esc(F.asOf(payload.as_of))
      + (fx ? " · 환율 " + fx.toFixed(2) + "원 적용" : "") + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-stat__value--display v2-freshness-affected">' + F.amount(payload.total_assets_krw, "KRW") + "</div>"
      + (payload.day_change_pct != null
        ? '<div class="v2-updown ' + F.signClass(payload.day_change_pct) + '">' + F.arrow(payload.day_change_pct)
          + F.pct(payload.day_change_pct) + " 전일 스냅샷 대비</div>"
        : "")
      + ((payload.missing_roles || []).length
        ? '<span class="v2-partial-note">' + esc(payload.missing_roles.join("·")) + " 계좌 결측 · 확보분 합계</span>"
        : "")
      + rows
      + allocationBarHtml()
      + "</div></div>";
  }

  /** 통합 자산 구성 — Asset §3-5와 동일한 전역 컴포넌트(00 §8-5)를 상속한다. */
  function allocationBarHtml() {
    var withWeight = accounts.filter(function (a) { return a.weight_pct != null; })
      .sort(function (x, y) { return y.weight_pct - x.weight_pct; });
    if (!withWeight.length) return "";
    var segs = withWeight.map(function (a, i) {
      return '<div class="v2-alloc-bar__seg" style="width:' + a.weight_pct + "%;background:"
        + SERIES[Math.min(i, SERIES.length - 1)] + '" title="' + esc(a.label) + " "
        + a.weight_pct.toFixed(1) + '%"></div>';
    }).join("");
    var legend = withWeight.map(function (a, i) {
      return '<span class="v2-alloc-legend__item"><span class="v2-alloc-legend__chip" style="background:'
        + SERIES[Math.min(i, SERIES.length - 1)] + '"></span>' + esc(a.label)
        + ' <span class="v2-alloc-legend__pct">' + a.weight_pct.toFixed(1) + "%</span></span>";
    }).join("");
    return '<div class="v2-alloc-bar v2-alloc-bar--slim" style="margin-top:16px">' + segs + "</div>"
      + '<div class="v2-alloc-legend">' + legend + "</div>";
  }

  // ── 계좌 탭(§3-2) ── 역할까지 붙여 "한국투자"가 두 개로 보이는 모호함을 없앤다.
  function tabsHtml() {
    return accounts.map(function (a) {
      return '<button type="button" class="v2-filter-chip" data-role="' + esc(a.role) + '" role="tab"'
        + ' aria-selected="' + (a.role === activeRole ? "true" : "false") + '"'
        + ' aria-pressed="' + (a.role === activeRole ? "true" : "false") + '">'
        + esc(a.label) + " · " + esc(a.sub_label) + "</button>";
    }).join("");
  }

  // ── Compact 4카드(§3-3) ── 확보되지 않은 값은 카드를 그리지 않는다.
  function compactCardsHtml(a) {
    var ccy = accountCurrency(a);
    var cards = [];
    cards.push(compact("계좌 평가액", F.amount(a.balance_krw, "KRW"),
      a.change_pct != null
        ? '<span class="v2-updown ' + F.signClass(a.change_pct) + '">' + F.arrow(a.change_pct)
          + F.pct(a.change_pct) + " 전일 대비</span>" : ""));
    if (a.deposit_krw != null || a.deposit_usd != null) {
      var dep = a.deposit_krw != null ? F.amount(a.deposit_krw, "KRW") : F.amount(a.deposit_usd, ccy);
      // 예수금이 평가액에 이미 포함된 계좌(KIS 국내 tot_evlu_amt, 실측)는 그 사실을 밝힌다 —
      // 안 밝히면 사용자가 평가액 + 예수금을 더해 자산을 과대 계산한다.
      var depSub = a.orderable_krw != null ? "주문가능 " + F.amount(a.orderable_krw, "KRW") : "";
      if (a.deposit_in_balance) {
        depSub += (depSub ? " · " : "") + "평가액에 포함됨";
      }
      cards.push(compact("예수금", dep, depSub));
    }
    if (a.eval_pnl_krw != null) {
      cards.push(compact("평가손익(누적)",
        '<span class="v2-updown ' + F.signClass(a.eval_pnl_krw) + '">' + F.signedAmount(a.eval_pnl_krw, "KRW") + "</span>",
        a.eval_pnl_pct != null
          ? '<span class="v2-updown ' + F.signClass(a.eval_pnl_pct) + '">' + F.arrow(a.eval_pnl_pct)
            + F.pct(a.eval_pnl_pct) + "</span>" : ""));
    }
    if (a.weight_pct != null) {
      cards.push(compact("전체 자산 대비 비중", a.weight_pct.toFixed(1) + "%",
        '<div class="v2-weight-bar" style="width:96px"><div class="v2-weight-bar__fill" style="width:'
        + a.weight_pct + '%"></div></div>'));
    }
    return cards.join("");
  }

  function compact(label, value, sub) {
    return '<div class="v2-card v2-card--standard v2-span-3">'
      + '<div class="v2-card__body"><span class="v2-stat__label">' + esc(label) + "</span>"
      + '<div class="v2-fs-value">' + value + "</div>"
      + (sub ? '<p class="v2-body v2-fs-sub">' + sub + "</p>" : "")
      + "</div></div>";
  }

  // ── 보유종목 테이블(§3-4) ──
  function holdingsTableHtml(a) {
    var rows = a.holdings || [];
    var ccy = accountCurrency(a);
    if (!rows.length) {
      return '<div class="v2-card v2-card--standard v2-span-8"><div class="v2-card__header">'
        + '<h3 class="v2-card__title">보유종목</h3></div><div class="v2-card__body">'
        + '<p class="v2-hub-empty">보유 중인 종목이 없습니다.</p></div></div>';
    }
    var sorted = rows.slice().sort(function (x, y) { return (holdingValue(y) || 0) - (holdingValue(x) || 0); });
    var body = sorted.map(function (h, i) {
      return '<tr class="v2-rank-row" data-holding="' + i + '" tabindex="0">'
        + '<td><span class="v2-rank-row__name">' + esc(h.name) + "</span>"
        + '<span class="v2-rank-row__code">' + esc(h.code) + "</span></td>"
        + '<td class="num">' + F.quantity(h.quantity) + "</td>"
        + '<td class="num">' + (h.avg_price != null ? F.amount(h.avg_price, ccy) : "—") + "</td>"
        + '<td class="num">' + (h.price != null ? F.amount(h.price, ccy) : "—") + "</td>"
        + '<td class="num">' + F.amount(holdingValue(h), ccy) + "</td>"
        + '<td class="num v2-updown ' + F.signClass(h.pnl_pct) + '">'
        + (h.pnl_pct != null ? F.arrow(h.pnl_pct) + F.pct(h.pnl_pct) : "—") + "</td>"
        + '<td class="num">' + weightCell(h.weight_pct) + "</td></tr>";
    }).join("");
    var total = sorted.reduce(function (acc, h) {
      var v = holdingValue(h);
      return v == null ? acc : acc + v;
    }, 0);
    return '<div class="v2-card v2-card--standard v2-span-8">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">보유종목 ' + sorted.length + "</h3>"
      + '<span class="v2-card__meta">' + esc(F.asOf(payload.as_of)) + "</span></div>"
      + '<div class="v2-card__body"><table class="v2-rank-table"><thead><tr>'
      + "<th>종목</th><th class=\"num\">수량</th><th class=\"num\">매입단가</th><th class=\"num\">현재가</th>"
      + "<th class=\"num\">평가금액</th><th class=\"num\">수익률</th><th class=\"num\">비중</th>"
      + "</tr></thead><tbody>" + body + "</tbody>"
      + '<tfoot><tr><td colspan="4">합계(예수금 제외)</td><td class="num">' + F.amount(total, ccy)
      + '</td><td colspan="2"></td></tr></tfoot></table></div></div>';
  }

  function weightCell(pct) {
    if (pct == null) return "—";
    return '<span class="v2-weight-cell">' + pct.toFixed(1) + "%"
      + '<span class="v2-weight-bar"><span class="v2-weight-bar__fill" style="width:'
      + Math.min(100, pct) + '%;display:block;height:100%"></span></span></span>';
  }

  // ── 계좌 내 비중 구성(§3-5) — 상위 4종목은 차트 팔레트, 5번째부터 '기타' 회색 묶음 ──
  function concentrationHtml(a) {
    var rows = (a.holdings || []).filter(function (h) { return h.weight_pct != null; })
      .sort(function (x, y) { return y.weight_pct - x.weight_pct; });
    if (!rows.length) return "";
    var top = rows.slice(0, 4);
    var restPct = rows.slice(4).reduce(function (acc, h) { return acc + h.weight_pct; }, 0);
    var segs = top.map(function (h, i) {
      // 12% 미만 조각에는 라벨을 넣지 않는다 — 텍스트가 조각보다 넓어져 잘린다(범례가 값을 진다).
      var label = h.weight_pct >= 12
        ? '<span class="v2-alloc-bar__seglabel">' + h.weight_pct.toFixed(0) + "%</span>" : "";
      return '<div class="v2-alloc-bar__seg" style="width:' + h.weight_pct + "%;background:" + SERIES[i]
        + '" title="' + esc(h.name) + " " + h.weight_pct.toFixed(1) + '%">' + label + "</div>";
    }).join("");
    if (restPct > 0) {
      segs += '<div class="v2-alloc-bar__seg" style="width:' + restPct.toFixed(1) + "%;background:" + OTHERS
        + '" title="기타 ' + (rows.length - 4) + "종목 " + restPct.toFixed(1) + '%">'
        + (restPct >= 12 ? '<span class="v2-alloc-bar__seglabel">' + restPct.toFixed(0) + "%</span>" : "")
        + "</div>";
    }
    var legend = top.map(function (h, i) {
      return '<span class="v2-alloc-legend__item"><span class="v2-alloc-legend__chip" style="background:'
        + SERIES[i] + '"></span>' + esc(h.name) + ' <span class="v2-alloc-legend__pct">'
        + h.weight_pct.toFixed(1) + "%</span></span>";
    }).join("");
    if (restPct > 0) {
      legend += '<span class="v2-alloc-legend__item"><span class="v2-alloc-legend__chip" style="background:'
        + OTHERS + '"></span>기타 ' + (rows.length - 4) + '종목 <span class="v2-alloc-legend__pct">'
        + restPct.toFixed(1) + "%</span></span>";
    }
    // 집중도 캡션 — violet 해석 레이어를 쓰지 않는다(design/09 §5-4의 절제 결정)
    var top1 = rows[0].weight_pct;
    var note = top1 > 40
      ? '<p class="v2-alloc-note" style="color:var(--status-warning)">상위 1종목 ' + top1.toFixed(1) + "% — 쏠림 주의</p>"
      : '<p class="v2-alloc-note">쏠림 주의 없음(상위 1종목 ' + top1.toFixed(1) + "%)</p>";
    return '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">비중 구성</h3></div>'
      + '<div class="v2-card__body"><div class="v2-alloc-bar">' + segs + "</div>"
      + '<div class="v2-alloc-legend">' + legend + "</div>" + note + "</div></div>";
  }

  // ── 종목 상세 패널(§3-6) ──
  // Stock Hub 전역 컴포넌트(stockhub.js)가 시세·뉴스·일정·ActionHub를 담당하고, 여기서는
  // Portfolio 고유의 PositionBlock 한 겹만 만든다(§1-3 "재발명하지 않는다").
  function openPositionPanel(account, holding) {
    if (!panelSlot) return;
    var ccy = accountCurrency(account);
    var purchase = (holding.avg_price != null && holding.quantity != null)
      ? holding.avg_price * holding.quantity : null;
    panelSlot.innerHTML = '<aside class="v2-hub-panel" role="dialog" aria-modal="true" aria-label="'
      + esc(holding.name) + ' 보유 상세" tabindex="-1">'
      + '<div class="v2-hub-panel__header">'
      + '<div><div class="v2-hub-panel__name">' + esc(holding.name) + "</div>"
      + '<div class="v2-hub-panel__meta">' + esc(holding.code) + " · " + esc(account.label) + "</div></div>"
      + '<button type="button" class="v2-hub-panel__close" data-panel-close aria-label="닫기">✕</button></div>'
      + '<div class="v2-hub-panel__body">'
      + '<div class="v2-hub-panel__price">' + F.amount(holding.price, ccy) + "</div>"
      + '<div class="v2-hub-panel__asof">' + esc(F.asOf(payload.as_of)) + "</div>"
      + '<div class="v2-hub-section"><div class="v2-hub-section__title">보유 정보</div>'
      + '<div class="v2-position-grid">'
      + posCell("매입단가", F.amount(holding.avg_price, ccy))
      + posCell("보유수량", F.quantity(holding.quantity))
      + posCell("매입금액", F.amount(purchase, ccy))
      + posCell("현재가", F.amount(holding.price, ccy))
      + posCell("실제 가치(평가)", F.amount(holdingValue(holding), ccy))
      + posCell("수익률", '<span class="v2-updown ' + F.signClass(holding.pnl_pct) + '">'
        + (holding.pnl_pct != null ? F.arrow(holding.pnl_pct) + F.pct(holding.pnl_pct) : "—") + "</span>")
      + "</div></div>"
      + '<div class="v2-hub-section"><div class="v2-hub-section__title">종목 분석</div>'
      + (holding.code
        ? '<div class="v2-hub-actions"><a class="v2-btn v2-btn--primary" target="_blank" rel="noopener"'
          + ' href="https://www.tradingview.com/chart/?symbol=' + esc(tvSymbol(account, holding))
          + '">▶ TradingView 차트 ↗</a></div>'
        : '<p class="v2-hub-empty">이 자산은 외부 차트 심볼이 없습니다.</p>')
      + "</div></div></aside>";
    panelSlot.setAttribute("data-masked", global.TAAssetGate.masked() ? "1" : "0");
    var panel = panelSlot.querySelector(".v2-hub-panel");
    if (panel) panel.focus();
  }

  function posCell(label, value) {
    return "<div><span class=\"v2-position-grid__label\">" + esc(label) + "</span>"
      + '<span class="v2-position-grid__value">' + value + "</span></div>";
  }

  function tvSymbol(account, holding) {
    if (account.role === "bybit") return "BYBIT:" + holding.code + "USDT";
    if (account.role === "kis_foreign") return holding.code;
    return "KRX:" + holding.code;
  }

  function closePanel() {
    if (panelSlot) panelSlot.innerHTML = "";
  }

  // ── 렌더 ──
  function renderActiveAccount() {
    var a = activeAccount();
    tabsEl.innerHTML = tabsHtml();
    heroEl.innerHTML = heroHtml();
    contentEl.innerHTML = a
      ? compactCardsHtml(a) + holdingsTableHtml(a) + concentrationHtml(a)
      : '<p class="v2-hub-empty">계좌 정보가 없습니다.</p>';
    applyMaskState();
    if (global.TAFreshness) global.TAFreshness.init(contentWrap);
  }

  function render(data) {
    payload = data;
    accounts = ordered(data.accounts || []);
    if (!activeRole || !activeAccount()) {
      var hash = (global.location.hash || "").replace("#", "");
      activeRole = accounts.filter(function (a) { return a.role === hash; }).length
        ? hash : (accounts.length ? accounts[0].role : null);
    }
    contentWrap.hidden = false;
    overlay.hidden = true;
    global.TAAssetGate.paintNavLocks(true);
    renderActiveAccount();
    if (stopIdle) stopIdle();
    stopIdle = global.TAAssetGate.startIdleLock(instantLock);
  }

  function applyMaskState() {
    var masked = global.TAAssetGate.masked();
    contentWrap.setAttribute("data-masked", masked ? "1" : "0");
    if (panelSlot) panelSlot.setAttribute("data-masked", masked ? "1" : "0");
    maskToggle.setAttribute("aria-pressed", masked ? "true" : "false");
  }

  function toggleMask() {
    global.TAAssetGate.setMasked(!global.TAAssetGate.masked());
    applyMaskState();
  }

  function instantLock() {
    global.TAAssetGate.lock();
    closePanel();
    contentWrap.hidden = true;
    heroEl.innerHTML = "";
    contentEl.innerHTML = "";
    tabsEl.innerHTML = "";
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

  function selectRole(role) {
    activeRole = role;
    global.location.hash = role;  // 뒤로 가기·새로고침 시 계좌 유지(§3-2)
    closePanel();
    renderActiveAccount();
  }

  function init() {
    overlay = doc.getElementById("portfolio-gate-overlay");
    form = doc.getElementById("portfolio-gate-form");
    input = doc.getElementById("portfolio-gate-input");
    errorEl = doc.getElementById("portfolio-gate-error");
    contentWrap = doc.getElementById("portfolio-content-wrap");
    heroEl = doc.getElementById("portfolio-hero");
    tabsEl = doc.querySelector("[data-account-tabs]");
    contentEl = doc.getElementById("portfolio-content");
    maskToggle = doc.getElementById("portfolio-mask-toggle");
    lockBtn = doc.getElementById("portfolio-lock-btn");
    panelSlot = doc.getElementById("panel-slot");
    if (!overlay || !form || !contentEl) return;

    form.addEventListener("submit", onSubmit);
    maskToggle.addEventListener("click", toggleMask);
    lockBtn.addEventListener("click", instantLock);
    global.TAAssetGate.bindModal(overlay, input, null);

    tabsEl.addEventListener("click", function (e) {
      var btn = e.target.closest ? e.target.closest("[data-role]") : null;
      if (btn) selectRole(btn.getAttribute("data-role"));
    });
    heroEl.addEventListener("click", function (e) {
      var row = e.target.closest ? e.target.closest("[data-goto]") : null;
      if (row) selectRole(row.getAttribute("data-goto"));
    });
    contentEl.addEventListener("click", function (e) {
      var tr = e.target.closest ? e.target.closest("[data-holding]") : null;
      if (!tr) return;
      var a = activeAccount();
      if (!a) return;
      var sorted = (a.holdings || []).slice().sort(function (x, y) {
        return (holdingValue(y) || 0) - (holdingValue(x) || 0);
      });
      openPositionPanel(a, sorted[parseInt(tr.getAttribute("data-holding"), 10)]);
    });
    doc.addEventListener("click", function (e) {
      if (e.target.closest && e.target.closest("[data-panel-close]")) closePanel();
    });
    doc.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closePanel();
      if (e.key === "H" && e.shiftKey && !contentWrap.hidden) toggleMask();
    });

    // Asset에서 이미 해제된 세션이면 재인증 없이 바로 연다(design/08 §1 게이트 세션 공유).
    global.TAAssetGate.tryAutoUnlock().then(function (data) {
      if (data) render(data);
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
