// portfolio.js — Portfolio 종목 단면(design/09, design/20 Phase 8). Asset과 같은 암호문
// (assets.enc.json)·같은 게이트 세션(sessionStorage, asset-gate.js 공유)을 쓴다 — Asset에서
// 이미 해제했다면 이 페이지는 재인증 없이 tryAutoUnlock()만으로 바로 열린다(design/08 §1).
// 계좌 탭으로 전환하며 각 계좌의 보유종목 테이블을 보여준다. 외부 라이브러리 0.
(function (global) {
  "use strict";

  var doc = global.document;
  var MASK_KEY = "ta:assetMasked"; // asset.js와 동일 키 — 두 페이지가 마스킹 상태도 공유한다
  var overlay, form, input, errorEl, contentWrap, tabsEl, contentEl, maskToggle, lockBtn;
  var accounts = [];
  var activeRole = null;

  function escapeHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function moneyKrw(v) {
    return v == null ? "—" : "₩" + Math.round(v).toLocaleString("ko-KR");
  }

  function amountSpan(formatted, symbol) {
    return '<span class="v2-amount"><span class="v2-amount__real">' + escapeHtml(formatted) + "</span>"
      + '<span class="v2-amount__masked">' + symbol + "••••••</span></span>";
  }

  function pct(v) {
    if (v == null) return "—";
    return (v >= 0 ? "+" : "−") + Math.abs(v).toFixed(2) + "%";
  }

  function signClass(v) {
    return v == null ? "flat" : v >= 0 ? "up" : "down";
  }

  function tabsHtml() {
    return accounts.map(function (a) {
      return '<button type="button" class="v2-filter-chip" data-role="' + a.role + '" role="tab" aria-pressed="'
        + (a.role === activeRole ? "true" : "false") + '">' + escapeHtml(a.label) + "</button>";
    }).join("");
  }

  function holdingsTableHtml(account) {
    var rows = account.holdings || [];
    var valueKey = account.native_currency === "USD" || account.native_currency === "USDT" ? "value_usd" : "value_krw";
    var symbol = account.native_currency === "KRW" ? "₩" : "$";
    if (!rows.length) {
      return '<p class="v2-hub-empty">이 계좌의 보유 종목 정보가 없습니다.</p>';
    }
    var body = rows.map(function (r) {
      return "<tr><td><span class=\"v2-rank-row__name\">" + escapeHtml(r.name) + "</span><span class=\"v2-rank-row__code\">"
        + escapeHtml(r.code) + "</span></td><td class=\"num\">" + (r.quantity != null ? r.quantity : "—")
        + '</td><td class="num">' + amountSpan(symbol + (r[valueKey] != null ? Math.round(r[valueKey]).toLocaleString("ko-KR") : "—"), "")
        + '</td><td class="num v2-updown ' + signClass(r.eval_pnl_krw) + '">'
        + (r.eval_pnl_krw != null ? amountSpan(moneyKrw(r.eval_pnl_krw), "₩") : "—") + "</td></tr>";
    }).join("");
    return '<table class="v2-rank-table"><thead><tr><th>종목</th><th class="num">수량</th><th class="num">평가금액</th><th class="num">평가손익</th></tr></thead><tbody>' + body + "</tbody></table>";
  }

  function accountSummaryHtml(account) {
    return '<div class="v2-card v2-card--standard v2-span-12">'
      + '<div class="v2-card__header"><h3 class="v2-card__title">' + escapeHtml(account.label) + "</h3><span class=\"v2-card__meta\">" + escapeHtml(account.sub_label) + "</span></div>"
      + '<div class="v2-card__body">'
      + '<div class="v2-fs-value">' + amountSpan(moneyKrw(account.balance_krw), "₩") + "</div>"
      + '<div class="v2-updown ' + signClass(account.change_pct) + '">' + pct(account.change_pct) + " 전일 대비</div>"
      + holdingsTableHtml(account)
      + "</div></div>";
  }

  function renderActiveAccount() {
    var account = accounts.filter(function (a) { return a.role === activeRole; })[0];
    tabsEl.innerHTML = tabsHtml();
    contentEl.innerHTML = account ? accountSummaryHtml(account) : '<p class="v2-hub-empty">계좌 정보가 없습니다.</p>';
    applyMaskState();
  }

  function maskState() {
    try { return global.sessionStorage.getItem(MASK_KEY) === "1"; } catch (e) { return false; }
  }

  function applyMaskState() {
    var masked = maskState();
    contentEl.setAttribute("data-masked", masked ? "1" : "0");
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

  function render(payload) {
    accounts = payload.accounts || [];
    activeRole = accounts.length ? accounts[0].role : null;
    contentWrap.hidden = false;
    overlay.hidden = true;
    renderActiveAccount();
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
    overlay = doc.getElementById("portfolio-gate-overlay");
    form = doc.getElementById("portfolio-gate-form");
    input = doc.getElementById("portfolio-gate-input");
    errorEl = doc.getElementById("portfolio-gate-error");
    contentWrap = doc.getElementById("portfolio-content-wrap");
    tabsEl = doc.querySelector("[data-account-tabs]");
    contentEl = doc.getElementById("portfolio-content");
    maskToggle = doc.getElementById("portfolio-mask-toggle");
    lockBtn = doc.getElementById("portfolio-lock-btn");
    if (!overlay || !form || !contentEl) return;

    form.addEventListener("submit", onSubmit);
    maskToggle.addEventListener("click", toggleMask);
    lockBtn.addEventListener("click", instantLock);
    tabsEl.addEventListener("click", function (e) {
      var btn = e.target.closest("[data-role]");
      if (!btn) return;
      activeRole = btn.getAttribute("data-role");
      renderActiveAccount();
    });

    // Asset에서 이미 해제된 세션이면 재인증 없이 바로 연다(design/08 §1 게이트 세션 공유).
    global.TAAssetGate.tryAutoUnlock().then(function (data) {
      if (data) render(data);
    });
  }

  if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", init);
  else init();
})(window);
