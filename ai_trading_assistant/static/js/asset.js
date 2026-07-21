// asset.js — Asset 페이지 렌더링(design/08, design/20 Phase 8). 게이트/암호화는
// asset-gate.js가 담당하고, 여기는 복호화된 payload를 화면에 그리는 것만 한다.
// [금액 가리기]는 값을 다시 그리지 않고 CSS로 절대금액만 도트로 치환한다(design/08 §1-3 —
// 고정 6도트, 콤마·공백 없음. 상대값(%)은 항상 유지). 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var MASK_KEY = "ta:assetMasked";
  var overlay, form, input, errorEl, content, contentWrap, maskToggle, lockBtn;
  var currentPayload = null;

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function moneyKrw(v) {
    return v == null ? "—" : "₩" + Math.round(v).toLocaleString("ko-KR");
  }

  function moneyUsd(v) {
    return v == null ? "—" : "$" + v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function pct(v) {
    if (v == null) return "—";
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%";
  }

  function signClass(v) {
    return v == null ? "flat" : v >= 0 ? "up" : "down";
  }

  // 실제 값(.v2-amount__real)과 고정 6도트 마스킹 값(.v2-amount__masked)을 함께 그려 두고,
  // #asset-content의 data-masked 속성으로 어느 쪽을 보일지 CSS가 전환한다(재렌더 없음).
  function amountSpan(formatted, currencySymbol) {
    return '<span class="v2-amount"><span class="v2-amount__real">' + escapeHtml(formatted) + "</span>"
      + '<span class="v2-amount__masked">' + currencySymbol + "••••••</span></span>";
  }

  function heroHtml(p) {
    var goal = p.goal_progress_pct;
    return '<div class="v2-card v2-card--hero v2-span-8">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">자산 요약</h3><span class="v2-card__meta">' + escapeHtml(p.as_of) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-stat__value--display">' + amountSpan(moneyKrw(p.total_assets_krw), "₩") + "</div>"
      + '<div class="v2-updown ' + signClass(p.day_change_pct) + '">' + pct(p.day_change_pct) + " 전일 스냅샷 대비</div>"
      + '<div class="v2-stat-row">'
      + '<div class="v2-stat"><span class="v2-stat__label">총자산</span><span class="v2-stat__value">' + amountSpan(moneyKrw(p.total_assets_krw), "₩") + "</span></div>"
      + "</div></div></div>"
      + '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">목표 달성률</h3></div>'
      + '<div class="v2-card__body">'
      + (goal != null
        ? '<div class="v2-stat__value--display">' + goal.toFixed(1) + "%</div>"
          + '<div class="v2-hub-stat__label">현재 ' + amountSpan(moneyKrw(p.total_assets_krw), "₩") + " · 목표 " + amountSpan(moneyKrw(p.goal_amount_krw), "₩") + "</div>"
        : '<p class="v2-hub-empty">목표 금액이 설정되지 않았습니다.</p>')
      + "</div></div>";
  }

  function accountCardHtml(a) {
    var currencyMap = { KRW: "₩", USD: "$", USDT: "$" };
    var symbol = currencyMap[a.native_currency] || "₩";
    return '<div class="v2-card v2-card--standard v2-span-4">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">' + escapeHtml(a.label) + "</h3><span class=\"v2-card__meta\">" + escapeHtml(a.sub_label) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-fs-value">' + amountSpan(moneyKrw(a.balance_krw), symbol) + "</div>"
      + '<div class="v2-updown ' + signClass(a.change_pct) + '">' + pct(a.change_pct) + " 전일 대비</div>"
      + (a.eval_pnl_krw != null
        ? '<p class="v2-body v2-fs-sub">평가손익 ' + amountSpan(moneyKrw(a.eval_pnl_krw), "₩") + " (" + pct(a.eval_pnl_pct) + ")</p>"
        : "")
      + (a.weight_pct != null ? '<p class="v2-body v2-fs-sub">비중 ' + a.weight_pct.toFixed(1) + "%</p>" : "")
      + (a.fx_rate ? '<p class="v2-body v2-fs-sub">적용 환율 ' + a.fx_rate.toFixed(2) + "원</p>" : "")
      + "</div></div>";
  }

  function currencyExposureHtml(list) {
    if (!list || !list.length) return "";
    var rows = list.map(function (e) {
      return '<div class="v2-macro-item__row"><span class="k">' + escapeHtml(e.currency) + '</span><span class="v">'
        + amountSpan(moneyKrw(e.amount_krw), "₩") + " (" + e.pct.toFixed(1) + "%)</span></div>";
    }).join("");
    return '<div class="v2-card v2-card--standard v2-span-12">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">통화 노출</h3></div>'
      + '<div class="v2-card__body">' + rows + "</div></div>";
  }

  function render(payload) {
    currentPayload = payload;
    var html = heroHtml(payload)
      + payload.accounts.map(accountCardHtml).join("")
      + currencyExposureHtml(payload.currency_exposure);
    content.innerHTML = html;
    contentWrap.hidden = false;
    overlay.hidden = true;
    applyMaskState();
  }

  function maskState() {
    try { return global.sessionStorage.getItem(MASK_KEY) === "1"; } catch (e) { return false; }
  }

  function applyMaskState() {
    var masked = maskState();
    content.setAttribute("data-masked", masked ? "1" : "0");
    maskToggle.setAttribute("aria-pressed", masked ? "true" : "false");
  }

  function toggleMask() {
    var next = !maskState();
    try { global.sessionStorage.setItem(MASK_KEY, next ? "1" : "0"); } catch (e) { /* noop */ }
    applyMaskState();
  }

  function instantLock() {
    global.TAAssetGate.lock();
    contentWrap.hidden = true;
    overlay.hidden = false;
    input.value = "";
    input.focus();
  }

  function showError() {
    errorEl.hidden = false;
    input.value = "";
    input.select();
    input.focus();
  }

  function onSubmit(e) {
    e.preventDefault();
    errorEl.hidden = true;
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
    doc.addEventListener("keydown", function (e) {
      if (e.key === "h" && e.shiftKey && !contentWrap.hidden) toggleMask(); // Shift+H(design/08 §1-3)
    });

    global.TAAssetGate.tryAutoUnlock().then(function (data) {
      if (data) render(data);
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
