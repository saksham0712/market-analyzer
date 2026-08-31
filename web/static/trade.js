/**
 * Paper trade simulator — Nifty 50 options (Phase A + B)
 * Wallet & positions in localStorage; chain from /api/trade/chain
 */

const STORAGE_KEY = "paper_trade_v1";
const LOT_SIZE = 50;
const STARTING_CASH = 100_000;

let chainData = null;
let activeExpiry = null;
let chainByExpiry = {};
let toastTimer = null;

const $ = (id) => document.getElementById(id);

const MONTHS = {
  Jan: 0,
  Feb: 1,
  Mar: 2,
  Apr: 3,
  May: 4,
  Jun: 5,
  Jul: 6,
  Aug: 7,
  Sep: 8,
  Oct: 9,
  Nov: 10,
  Dec: 11,
};

function defaultState() {
  return {
    cash: STARTING_CASH,
    realizedPnl: 0,
    positions: [],
    closedTrades: [],
  };
}

function loadState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return defaultState();
    const parsed = JSON.parse(raw);
    return {
      cash: Number(parsed.cash ?? STARTING_CASH),
      realizedPnl: Number(parsed.realizedPnl ?? 0),
      positions: Array.isArray(parsed.positions) ? parsed.positions : [],
      closedTrades: Array.isArray(parsed.closedTrades) ? parsed.closedTrades : [],
    };
  } catch {
    return defaultState();
  }
}

function saveState(state) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
}

function newId() {
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return `pos_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function sameStrike(a, b) {
  return Math.abs(Number(a) - Number(b)) < 0.001;
}

function fmtMoney(value) {
  const n = Number(value) || 0;
  const sign = n < 0 ? "-" : "";
  return `${sign}₹${Math.abs(n).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function showToast(message, type = "success") {
  const el = $("trade-toast");
  if (!el) return;
  el.textContent = message;
  el.className = `trade-toast ${type}`;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.classList.add("hidden");
  }, 3200);
}

function parseNseExpiry(value) {
  const match = String(value).match(/^(\d{2})-([A-Za-z]{3})-(\d{4})$/);
  if (!match) return null;
  const month = MONTHS[match[2]];
  if (month == null) return null;
  return new Date(Number(match[3]), month, Number(match[1]));
}

function expiryKind(expiry, index, all) {
  if (index === 0) return "nearest";
  if (index > 0) {
    const prev = parseNseExpiry(all[index - 1]);
    const cur = parseNseExpiry(expiry);
    if (prev && cur) {
      const days = (cur.getTime() - prev.getTime()) / 86400000;
      if (days > 10) return "monthly";
    }
  }
  return "weekly";
}

function formatExpiryTab(expiry, index, all) {
  const date = parseNseExpiry(expiry);
  const kind = expiryKind(expiry, index, all);
  const kindLabel = kind === "nearest" ? "Nearest" : kind === "monthly" ? "Monthly" : "Weekly";
  const dateLabel = date
    ? date.toLocaleDateString("en-IN", { weekday: "short", day: "numeric", month: "short" })
    : expiry;
  return { kindLabel, dateLabel, raw: expiry };
}

function getChainForExpiry(expiry) {
  if (expiry && chainByExpiry[expiry]) return chainByExpiry[expiry];
  if (expiry === activeExpiry && chainData) return chainData;
  return null;
}

function findLtp(type, strike, expiry = activeExpiry) {
  const chain = getChainForExpiry(expiry);
  if (!chain?.rows) return null;
  const row = chain.rows.find((r) => sameStrike(r.strike, strike));
  if (!row) return null;
  const leg = type === "CE" ? row.ce : row.pe;
  const ltp = leg?.ltp;
  return ltp != null ? Number(ltp) : null;
}

function premiumCost(ltp, lots) {
  return (Number(ltp) || 0) * LOT_SIZE * lots;
}

function computePositionMtm(position) {
  const ltp = findLtp(position.type, position.strike, position.expiry);
  if (ltp == null) return { ltp: null, mtm: null, marketValue: null };
  const qty = position.lots * LOT_SIZE;
  const mtm = (ltp - position.avgEntry) * qty;
  const marketValue = ltp * qty;
  return { ltp, mtm, marketValue };
}

function investedBasis(state) {
  return state.positions.reduce((sum, p) => sum + p.avgEntry * p.lots * LOT_SIZE, 0);
}

function totalUnrealized(state) {
  return state.positions.reduce((sum, p) => {
    const { mtm } = computePositionMtm(p);
    return sum + (mtm ?? 0);
  }, 0);
}

function renderStats(state) {
  const unrealized = totalUnrealized(state);
  const invested = investedBasis(state);

  $("stat-cash").textContent = fmtMoney(state.cash);
  $("stat-invested").textContent = fmtMoney(invested);
  const unrealEl = $("stat-unrealized");
  unrealEl.textContent = fmtMoney(unrealized);
  unrealEl.className = "stat-value" + (unrealized > 0 ? " positive" : unrealized < 0 ? " negative" : "");

  const realEl = $("stat-realized");
  realEl.textContent = fmtMoney(state.realizedPnl);
  realEl.className = "stat-value" + (state.realizedPnl > 0 ? " positive" : state.realizedPnl < 0 ? " negative" : "");
}

function renderPositions(state) {
  const container = $("positions-list");
  if (!state.positions.length) {
    container.innerHTML = '<p class="trade-empty">No open positions. Buy from the chain above.</p>';
    return;
  }

  container.innerHTML = state.positions
    .map((p) => {
      const { ltp, mtm } = computePositionMtm(p);
      const mtmClass = (mtm ?? 0) > 0 ? "positive" : (mtm ?? 0) < 0 ? "negative" : "";
      const expiryHint =
        p.expiry !== activeExpiry
          ? `<p class="field-hint">Expiry tab: ${p.expiry} (refresh or switch tab for latest LTP)</p>`
          : "";
      return `
        <article class="position-card" data-id="${p.id}">
          <div class="position-head">
            <span class="position-title">NIFTY ${p.strike} ${p.type}</span>
            <span class="position-badge ${p.type.toLowerCase()}">${p.type}</span>
          </div>
          <div class="position-grid">
            <div><span>Expiry</span><br>${p.expiry}</div>
            <div><span>Lots</span><br>${p.lots}</div>
            <div><span>Avg entry</span><br>${Number(p.avgEntry).toFixed(2)}</div>
            <div><span>LTP</span><br>${ltp != null ? ltp.toFixed(2) : "—"}</div>
            <div><span>MTM</span><br><strong class="stat-value ${mtmClass}">${mtm != null ? fmtMoney(mtm) : "—"}</strong></div>
          </div>
          ${expiryHint}
          <div class="position-actions">
            <button type="button" class="btn btn-primary btn-sm btn-exit" data-id="${p.id}">Exit</button>
          </div>
        </article>`;
    })
    .join("");

  container.querySelectorAll(".btn-exit").forEach((btn) => {
    btn.addEventListener("click", () => openExitSheet(btn.dataset.id));
  });
}

function renderClosed(state) {
  const container = $("closed-list");
  if (!state.closedTrades.length) {
    container.innerHTML = '<p class="trade-empty">No closed trades yet.</p>';
    return;
  }

  container.innerHTML = state.closedTrades
    .slice()
    .reverse()
    .map(
      (t) => `
      <article class="closed-card">
        <div class="position-head">
          <span class="position-title">${t.side} NIFTY ${t.strike} ${t.type}</span>
          <span class="position-badge ${t.type.toLowerCase()}">${t.lots} lot(s)</span>
        </div>
        <div class="position-grid">
          <div><span>Entry</span><br>${Number(t.entry).toFixed(2)}</div>
          <div><span>Exit</span><br>${Number(t.exit).toFixed(2)}</div>
          <div><span>P&amp;L</span><br><strong class="${t.pnl >= 0 ? "positive" : "negative"}">${fmtMoney(t.pnl)}</strong></div>
          <div><span>Time</span><br>${new Date(t.closedAt).toLocaleString("en-IN")}</div>
        </div>
      </article>`
    )
    .join("");
}

function renderExpiryTabs(expiries, selected) {
  const container = $("expiry-tabs");
  const list = expiries || [];
  container.innerHTML = list
    .map((exp, index) => {
      const label = formatExpiryTab(exp, index, list);
      const active = exp === selected ? " active" : "";
      return `<button type="button" class="expiry-tab${active}" data-expiry="${exp}" role="tab" title="${exp}">
        <span class="expiry-kind">${label.kindLabel}</span>
        <span class="expiry-date">${label.dateLabel}</span>
      </button>`;
    })
    .join("");

  container.querySelectorAll(".expiry-tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      if (tab.dataset.expiry === activeExpiry) return;
      loadChain(tab.dataset.expiry);
    });
  });
}

function renderChainTable() {
  const body = $("chain-body");
  if (!chainData?.rows?.length) {
    body.innerHTML = '<tr><td colspan="3" class="chain-loading">No chain data</td></tr>';
    return;
  }

  const spot = chainData.spot;
  let atmStrike = chainData.rows[0]?.strike;
  if (spot != null) {
    atmStrike = chainData.rows.reduce((best, row) =>
      Math.abs(row.strike - spot) < Math.abs(best.strike - spot) ? row : best
    ).strike;
  }

  body.innerHTML = chainData.rows
    .map((row) => {
      const ceLtp = row.ce?.ltp;
      const peLtp = row.pe?.ltp;
      const atm = sameStrike(row.strike, atmStrike) ? " atm" : "";
      const ceDisabled = ceLtp == null || ceLtp <= 0;
      const peDisabled = peLtp == null || peLtp <= 0;
      return `
        <tr class="${atm.trim()}">
          <td>
            <button type="button" class="chain-leg-btn ce" data-type="CE" data-strike="${row.strike}"
              data-ltp="${ceLtp ?? ""}" ${ceDisabled ? "disabled" : ""}>
              ${ceLtp != null ? Number(ceLtp).toFixed(2) : "—"}
            </button>
          </td>
          <td class="strike-cell">${row.strike}</td>
          <td>
            <button type="button" class="chain-leg-btn pe" data-type="PE" data-strike="${row.strike}"
              data-ltp="${peLtp ?? ""}" ${peDisabled ? "disabled" : ""}>
              ${peLtp != null ? Number(peLtp).toFixed(2) : "—"}
            </button>
          </td>
        </tr>`;
    })
    .join("");

  body.querySelectorAll(".chain-leg-btn").forEach((btn) => {
    btn.addEventListener("click", (event) => {
      event.preventDefault();
      event.stopPropagation();
      if (btn.disabled) return;
      const type = btn.dataset.type;
      const strike = Number(btn.dataset.strike);
      const ltp = Number(btn.dataset.ltp);
      if (!Number.isFinite(ltp) || ltp <= 0) {
        showToast("LTP not available for this strike.", "error");
        return;
      }
      openOrderSheet(type, strike, ltp);
    });
  });
}

async function ensureChainForExpiry(expiry) {
  if (!expiry) return getChainForExpiry(activeExpiry);
  if (chainByExpiry[expiry]) return chainByExpiry[expiry];

  const params = new URLSearchParams({ expiry });
  const res = await fetch(`/api/trade/chain?${params}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Failed to load chain for expiry");

  chainByExpiry[data.expiry] = data;
  if (data.expiry === activeExpiry) {
    chainData = data;
  }
  return data;
}

async function fetchLiveLtp(expiry, strike, type) {
  const params = new URLSearchParams({
    expiry,
    strike: String(strike),
    type,
  });
  const res = await fetch(`/api/trade/quote?${params}`, { cache: "no-store" });
  const data = await res.json();
  if (!res.ok) {
    const detail = data.detail;
    throw new Error(typeof detail === "string" ? detail : "Could not fetch live LTP");
  }
  return data;
}

function updateChainLtp(expiry, strike, type, ltp) {
  const chain = getChainForExpiry(expiry);
  if (!chain?.rows) return;
  const row = chain.rows.find((r) => sameStrike(r.strike, strike));
  if (!row) return;
  const legKey = type === "CE" ? "ce" : "pe";
  if (!row[legKey]) row[legKey] = {};
  row[legKey].ltp = ltp;
  chainByExpiry[expiry] = chain;
  if (expiry === activeExpiry) {
    chainData = chain;
    renderChainTable();
  }
}

function setSubmitLoading(buttonId, loading, loadingText = "Working…") {
  const btn = $(buttonId);
  if (!btn) return;
  if (loading) {
    if (!btn.dataset.originalText) btn.dataset.originalText = btn.textContent;
    btn.textContent = loadingText;
    btn.disabled = true;
  } else {
    btn.textContent = btn.dataset.originalText || btn.textContent;
    btn.disabled = false;
  }
}

async function loadChain(expiry = null, refresh = false) {
  const errEl = $("chain-error");
  errEl.classList.add("hidden");
  $("chain-body").innerHTML = '<tr><td colspan="3" class="chain-loading">Loading chain…</td></tr>';

  const params = new URLSearchParams();
  if (expiry) params.set("expiry", expiry);
  if (refresh) params.set("refresh", "true");

  try {
    const res = await fetch(`/api/trade/chain?${params}`, { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Failed to load chain");

    chainData = data;
    chainByExpiry[data.expiry] = data;
    activeExpiry = data.expiry;
    $("spot-value").textContent = data.spot != null ? data.spot.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : "—";

    const activeLabel = formatExpiryTab(data.expiry, (data.expiries || []).indexOf(data.expiry), data.expiries || []);
    let meta = `Showing: ${activeLabel.kindLabel} · ${activeLabel.dateLabel}`;
    if (data.source) meta += ` · ${data.source.toUpperCase()}`;
    if (data.cached) meta += " · cached";
    if (data.stale) meta += " · stale";
    if (data.fallback) meta += " · fallback";
    if (data.warning) {
      errEl.textContent = data.warning;
      errEl.classList.remove("hidden");
    }
    $("chain-meta").textContent = meta;

    renderExpiryTabs(data.expiries || [data.expiry], data.expiry);
    renderChainTable();

    const state = loadState();
    renderStats(state);
    renderPositions(state);
  } catch (err) {
    errEl.textContent = err.message || "Could not load option chain";
    errEl.classList.remove("hidden");
    $("chain-body").innerHTML = '<tr><td colspan="3" class="chain-loading">Failed to load</td></tr>';
  }
}

function showSheet(sheetId) {
  $("sheet-backdrop").classList.remove("hidden");
  $("order-sheet").classList.add("hidden");
  $("exit-sheet").classList.add("hidden");
  $(sheetId).classList.remove("hidden");
  document.body.style.overflow = "hidden";
}

function hideSheets() {
  $("sheet-backdrop").classList.add("hidden");
  $("order-sheet").classList.add("hidden");
  $("exit-sheet").classList.add("hidden");
  document.body.style.overflow = "";
}

function openOrderSheet(type, strike, ltp) {
  $("order-type").value = type;
  $("order-strike").value = String(strike);
  $("order-expiry").value = activeExpiry || "";
  $("order-ltp").value = String(ltp);
  $("order-lots").value = "1";
  $("order-sheet-title").textContent = `Buy ${type}`;
  $("order-sheet-subtitle").textContent = `NIFTY ${strike} ${type} · ${activeExpiry} · Chain LTP ${Number(ltp).toFixed(2)}`;
  updateOrderEstimate();
  showSheet("order-sheet");
  refreshOrderSheetLtp(type, strike, activeExpiry, ltp);
}

async function refreshOrderSheetLtp(type, strike, expiry, fallbackLtp) {
  if (!expiry) return;
  try {
    const quote = await fetchLiveLtp(expiry, strike, type);
    const liveLtp = Number(quote.ltp);
    if (!Number.isFinite(liveLtp) || liveLtp <= 0) return;
    updateChainLtp(expiry, strike, type, liveLtp);
    if ($("order-sheet").classList.contains("hidden")) return;
    if ($("order-type").value !== type || !sameStrike($("order-strike").value, strike)) return;
    $("order-ltp").value = String(liveLtp);
    $("order-sheet-subtitle").textContent = `NIFTY ${strike} ${type} · ${expiry} · Live LTP ${liveLtp.toFixed(2)}`;
    updateOrderEstimate();
  } catch {
    $("order-ltp").value = String(fallbackLtp);
    updateOrderEstimate();
  }
}

function updateOrderEstimate() {
  const ltp = Number($("order-ltp").value);
  const lots = Math.max(1, parseInt($("order-lots").value, 10) || 1);
  $("order-estimate").textContent = fmtMoney(premiumCost(ltp, lots));
}

async function executeBuy(event) {
  event.preventDefault();
  if ($("order-submit")?.disabled) return;

  try {
    const type = $("order-type").value;
    const strike = Number($("order-strike").value);
    const expiry = $("order-expiry").value;
    const lots = Math.max(1, parseInt($("order-lots").value, 10) || 1);

    if (!type || !expiry || !Number.isFinite(strike)) {
      showToast("Invalid order. Refresh chain and try again.", "error");
      return;
    }

    setSubmitLoading("order-submit", true, "Fetching live LTP…");
    let quote;
    try {
      quote = await fetchLiveLtp(expiry, strike, type);
    } finally {
      setSubmitLoading("order-submit", false);
    }

    const ltp = Number(quote.ltp);
    if (!Number.isFinite(ltp) || ltp <= 0) {
      showToast("Live LTP unavailable. Try again.", "error");
      return;
    }

    updateChainLtp(expiry, strike, type, ltp);
    $("order-ltp").value = String(ltp);

    const state = loadState();
    const cost = premiumCost(ltp, lots);
    if (cost > state.cash + 0.01) {
      showToast(`Not enough cash. Need ${fmtMoney(cost)}, have ${fmtMoney(state.cash)}.`, "error");
      return;
    }

    const existing = state.positions.find(
      (p) => p.type === type && sameStrike(p.strike, strike) && p.expiry === expiry
    );
    if (existing) {
      const totalLots = existing.lots + lots;
      const weighted = (existing.avgEntry * existing.lots + ltp * lots) / totalLots;
      existing.lots = totalLots;
      existing.avgEntry = weighted;
    } else {
      state.positions.push({
        id: newId(),
        type,
        strike,
        expiry,
        lots,
        avgEntry: ltp,
        openedAt: new Date().toISOString(),
      });
    }

    state.cash -= cost;
    saveState(state);
    hideSheets();
    renderStats(state);
    renderPositions(state);
    renderClosed(state);
    showToast(`Bought ${lots} lot(s) NIFTY ${strike} ${type} @ ${ltp.toFixed(2)} live`);
  } catch (err) {
    setSubmitLoading("order-submit", false);
    showToast(err.message || "Could not place buy order.", "error");
  }
}

async function openExitSheet(positionId) {
  const state = loadState();
  const position = state.positions.find((p) => p.id === positionId);
  if (!position) return;

  $("exit-position-id").value = positionId;
  $("exit-lots").value = String(position.lots);
  $("exit-lots").max = String(position.lots);
  $("exit-lots-hint").textContent = `Max ${position.lots} lot(s) · entry ${Number(position.avgEntry).toFixed(2)}`;
  $("exit-sheet-subtitle").textContent = `NIFTY ${position.strike} ${position.type} · ${position.expiry} · fetching live LTP…`;
  $("exit-estimate").textContent = "—";
  $("exit-pnl-estimate").textContent = "—";
  showSheet("exit-sheet");

  try {
    const quote = await fetchLiveLtp(position.expiry, position.strike, position.type);
    const ltp = Number(quote.ltp);
    if (!Number.isFinite(ltp) || ltp <= 0) {
      throw new Error("Live LTP unavailable for this position.");
    }
    updateChainLtp(position.expiry, position.strike, position.type, ltp);
    $("exit-sheet-subtitle").textContent = `NIFTY ${position.strike} ${position.type} · ${position.expiry} · Live LTP ${ltp.toFixed(2)}`;
    updateExitEstimate();
  } catch (err) {
    hideSheets();
    showToast(err.message || "Could not fetch live LTP for exit.", "error");
  }
}

function updateExitEstimate() {
  const state = loadState();
  const positionId = $("exit-position-id").value;
  const position = state.positions.find((p) => p.id === positionId);
  if (!position) return;

  const lots = Math.min(position.lots, Math.max(1, parseInt($("exit-lots").value, 10) || 1));
  const ltp = findLtp(position.type, position.strike, position.expiry);
  if (ltp == null) return;

  const credit = premiumCost(ltp, lots);
  const pnl = (ltp - position.avgEntry) * LOT_SIZE * lots;
  $("exit-estimate").textContent = fmtMoney(credit);
  const pnlEl = $("exit-pnl-estimate");
  pnlEl.textContent = fmtMoney(pnl);
  pnlEl.className = pnl >= 0 ? "positive" : "negative";
}

async function executeExit(event) {
  event.preventDefault();
  if ($("exit-submit")?.disabled) return;

  try {
    const state = loadState();
    const positionId = $("exit-position-id").value;
    const position = state.positions.find((p) => p.id === positionId);
    if (!position) return;

    const exitLots = Math.min(position.lots, Math.max(1, parseInt($("exit-lots").value, 10) || 1));

    setSubmitLoading("exit-submit", true, "Fetching live LTP…");
    let quote;
    try {
      quote = await fetchLiveLtp(position.expiry, position.strike, position.type);
    } finally {
      setSubmitLoading("exit-submit", false);
    }

    const ltp = Number(quote.ltp);
    if (!Number.isFinite(ltp) || ltp <= 0) {
      showToast("Live LTP unavailable. Try again.", "error");
      return;
    }

    updateChainLtp(position.expiry, position.strike, position.type, ltp);

    const credit = premiumCost(ltp, exitLots);
    const pnl = (ltp - position.avgEntry) * LOT_SIZE * exitLots;

    state.cash += credit;
    state.realizedPnl += pnl;
    state.closedTrades.push({
      side: "SELL",
      type: position.type,
      strike: position.strike,
      expiry: position.expiry,
      lots: exitLots,
      entry: position.avgEntry,
      exit: ltp,
      pnl,
      closedAt: new Date().toISOString(),
    });

    if (exitLots >= position.lots) {
      state.positions = state.positions.filter((p) => p.id !== positionId);
    } else {
      position.lots -= exitLots;
    }

    saveState(state);
    hideSheets();
    renderStats(state);
    renderPositions(state);
    renderClosed(state);
    showToast(`Sold ${exitLots} lot(s) @ ${ltp.toFixed(2)} live · P&L ${fmtMoney(pnl)}`, pnl >= 0 ? "success" : "error");
  } catch (err) {
    setSubmitLoading("exit-submit", false);
    showToast(err.message || "Could not exit position.", "error");
  }
}

function resetAccount() {
  if (!confirm("Reset paper account to ₹1,00,000 and clear all positions?")) return;
  saveState(defaultState());
  const state = loadState();
  renderStats(state);
  renderPositions(state);
  renderClosed(state);
  showToast("Paper account reset to ₹1,00,000");
}

function init() {
  const state = loadState();
  renderStats(state);
  renderPositions(state);
  renderClosed(state);

  $("btn-refresh").addEventListener("click", () => loadChain(activeExpiry, true));
  $("btn-reset").addEventListener("click", resetAccount);
  $("sheet-backdrop").addEventListener("click", hideSheets);
  $("order-cancel").addEventListener("click", hideSheets);
  $("exit-cancel").addEventListener("click", hideSheets);
  $("order-form").addEventListener("submit", executeBuy);
  $("exit-form").addEventListener("submit", executeExit);
  $("order-lots").addEventListener("input", updateOrderEstimate);
  $("exit-lots").addEventListener("input", updateExitEstimate);

  loadChain();
}

document.addEventListener("DOMContentLoaded", init);
