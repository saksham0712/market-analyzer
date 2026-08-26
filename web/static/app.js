const form = document.getElementById("analyze-form");
const resultsEl = document.getElementById("results");
const errorBanner = document.getElementById("error-banner");
const errorMessage = document.getElementById("error-message");
const errorSuggestions = document.getElementById("error-suggestions");
const analyzeBtn = document.getElementById("analyze-btn");
const btnLabel = analyzeBtn.querySelector(".btn-label");
const btnSpinner = analyzeBtn.querySelector(".btn-spinner");

const MARKET_PLACEHOLDERS = {
  index: "e.g. NIFTY, BANKNIFTY, SENSEX",
  nse_stock: "e.g. RELIANCE, TCS, INFY",
  bse_stock: "e.g. 500325, 532540",
  etf: "e.g. UTI Gold ETF, TATAGOLD, GOLDBEES",
  us_stock: "e.g. Apple, AAPL, Microsoft",
  us_etf: "e.g. SPY, QQQ, GLD",
  us_index: "e.g. S&P 500, ^GSPC, NASDAQ",
  global_index: "e.g. ^FTSE, ^N225",
};

const marketTypeSelect = document.getElementById("market-type");
const symbolInput = document.getElementById("symbol");
const suggestionsEl = document.getElementById("suggestions");

let searchTimer = null;

async function parseApiResponse(response) {
  const text = await response.text();
  if (!text) {
    return { detail: `Empty response from server (${response.status})` };
  }
  try {
    return JSON.parse(text);
  } catch {
    const snippet = text.replace(/\s+/g, " ").trim().slice(0, 180);
    if (response.status >= 500) {
      return {
        detail:
          "Server error — the app may still be starting. Wait 30 seconds and try again. " +
          `(HTTP ${response.status})`,
      };
    }
    return { detail: snippet || `Unexpected response (HTTP ${response.status})` };
  }
}

function formatApiError(data, fallback = "Something went wrong. Please try again.") {
  if (!data) return fallback;
  if (typeof data.detail === "string") return data.detail;
  if (Array.isArray(data.detail)) {
    return data.detail
      .map((item) => (typeof item === "string" ? item : item.msg || JSON.stringify(item)))
      .join("; ");
  }
  if (data.message && typeof data.message === "string") return data.message;
  return fallback;
}

async function apiFetch(url, options = {}) {
  try {
    const response = await fetch(url, options);
    const data = await parseApiResponse(response);
    return { response, data, ok: response.ok };
  } catch (err) {
    return {
      response: null,
      data: {
        detail:
          "Cannot reach the server. Check your internet connection, or wait if the app just woke up from sleep.",
      },
      ok: false,
      networkError: err,
    };
  }
}

marketTypeSelect.addEventListener("change", () => {
  symbolInput.placeholder = MARKET_PLACEHOLDERS[marketTypeSelect.value] || "";
  hideSuggestions();
});

symbolInput.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const query = symbolInput.value.trim();
  if (query.length < 2) {
    hideSuggestions();
    return;
  }
  searchTimer = setTimeout(() => fetchSuggestions(query), 250);
});

symbolInput.addEventListener("blur", () => {
  setTimeout(hideSuggestions, 150);
});

document.addEventListener("click", (event) => {
  if (!event.target.closest(".symbol-field")) {
    hideSuggestions();
  }
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideError();
  hideSuggestions();
  setLoading(true);

  const symbol = symbolInput.value.trim();
  const market_type = marketTypeSelect.value;

  try {
    const { response, data, ok } = await apiFetch("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ symbol, market_type }),
    });

    if (!ok) {
      showError(formatApiError(data, "Analysis failed"), data.suggestions);
      resultsEl.classList.add("hidden");
      return;
    }

    renderResults(data);
    resultsEl.classList.remove("hidden");
    resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    showError(err.message || "Analysis failed");
    resultsEl.classList.add("hidden");
  } finally {
    setLoading(false);
  }
});

async function fetchSuggestions(query) {
  try {
    const params = new URLSearchParams({
      q: query,
      market_type: marketTypeSelect.value,
    });
    const { data, ok } = await apiFetch(`/api/search?${params}`);
    if (!ok) {
      hideSuggestions();
      return;
    }
    renderSuggestions(data.results || []);
  } catch {
    hideSuggestions();
  }
}

function renderSuggestions(results) {
  if (!results.length) {
    hideSuggestions();
    return;
  }

  suggestionsEl.innerHTML = results
    .map(
      (item) => `
      <li role="option" data-symbol="${item.symbol}" tabindex="0">
        <strong>${item.symbol}</strong>
        <span>${item.name}</span>
      </li>`
    )
    .join("");

  suggestionsEl.classList.remove("hidden");
  suggestionsEl.querySelectorAll("li").forEach((item) => {
    item.addEventListener("mousedown", (event) => {
      event.preventDefault();
      symbolInput.value = item.dataset.symbol;
      hideSuggestions();
    });
  });
}

function hideSuggestions() {
  suggestionsEl.classList.add("hidden");
  suggestionsEl.innerHTML = "";
}

function setLoading(loading) {
  analyzeBtn.disabled = loading;
  btnLabel.textContent = loading ? "Analyzing…" : "Analyze";
  btnSpinner.classList.toggle("hidden", !loading);
}

function showError(message, suggestions = []) {
  const text = typeof message === "string" ? message : message?.message || "Analysis failed";
  errorMessage.textContent = text;
  errorBanner.classList.remove("hidden");

  if (suggestions && suggestions.length) {
    errorSuggestions.innerHTML = suggestions
      .map(
        (item) =>
          `<button type="button" class="suggestion-chip" data-symbol="${item.symbol}">${item.symbol} — ${item.name}</button>`
      )
      .join("");
    errorSuggestions.classList.remove("hidden");
    errorSuggestions.querySelectorAll(".suggestion-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        symbolInput.value = chip.dataset.symbol;
        hideError();
        form.requestSubmit();
      });
    });
  } else {
    errorSuggestions.classList.add("hidden");
    errorSuggestions.innerHTML = "";
  }
}

function hideError() {
  errorBanner.classList.add("hidden");
  errorMessage.textContent = "";
  errorSuggestions.classList.add("hidden");
  errorSuggestions.innerHTML = "";
}

function fmt(value, suffix = "") {
  if (value === null || value === undefined) return "N/A";
  return `${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}${suffix}`;
}

function money(value, currency) {
  if (value === null || value === undefined) return "N/A";
  return `${currency} ${fmt(value)}`;
}

function range(low, high, currency) {
  if (low == null || high == null) return "N/A";
  return `${currency} ${fmt(low)} – ${fmt(high)}`;
}

function computeBuySellSplit(data) {
  const base = {
    STRONG_BUY: 88,
    BUY: 72,
    HOLD: 50,
    SELL: 28,
    STRONG_SELL: 12,
  };
  let buy = base[data.signal] ?? 50;

  if (typeof data.score === "number") {
    buy += data.score * 1.8;
  }
  if (data.confidence != null && data.signal !== "HOLD") {
    const tilt = ((data.confidence - 50) / 50) * 8;
    if (data.signal.includes("BUY")) buy += tilt;
    if (data.signal.includes("SELL")) buy -= tilt;
  }

  buy = Math.round(Math.max(6, Math.min(94, buy)));
  return { buy, sell: 100 - buy };
}

function renderSignalMeter(data) {
  const { buy, sell } = computeBuySellSplit(data);
  const sellEl = document.getElementById("signal-meter-sell");
  const buyEl = document.getElementById("signal-meter-buy");
  const trackEl = document.getElementById("signal-meter-track");
  const labelEl = document.getElementById("signal-meter-label");

  sellEl.style.width = `${sell}%`;
  buyEl.style.width = `${buy}%`;
  trackEl.setAttribute("aria-valuenow", String(buy));
  labelEl.textContent = data.signal.replace(/_/g, " ");
  labelEl.className = `signal-meter-label signal-${data.signal}`;
}

function renderResults(data) {
  renderSignalMeter(data);

  const sym = data.symbol;
  document.getElementById("display-name").textContent = sym.name;
  document.getElementById("symbol-meta").textContent =
    `${sym.input} · ${sym.exchange} · Yahoo: ${sym.yahoo}` +
    (data.resolved_from ? ` · matched: "${data.resolved_from}"` : "");

  document.getElementById("price").textContent = money(data.price, data.currency);

  const changeEl = document.getElementById("day-change");
  if (data.day_change_pct != null) {
    const sign = data.day_change_pct >= 0 ? "+" : "";
    changeEl.textContent = `${sign}${data.day_change_pct.toFixed(2)}% today`;
    changeEl.className =
      "day-change " + (data.day_change_pct > 0 ? "up" : data.day_change_pct < 0 ? "down" : "flat");
  } else {
    changeEl.textContent = "—";
    changeEl.className = "day-change flat";
  }

  const badge = document.getElementById("signal-badge");
  badge.textContent = data.signal.replace(/_/g, " ");
  badge.className = `signal-badge ${data.signal}`;

  document.getElementById("confidence").textContent = `${data.confidence}%`;
  document.getElementById("score").textContent = data.score;
  document.getElementById("raw-signal").textContent = data.raw_signal.replace(/_/g, " ");
  document.getElementById("conviction").textContent = data.conviction_met ? "Met" : "Not met";
  document.getElementById("summary").textContent = data.summary;
  document.getElementById("action-advice").textContent = data.action_advice;

  renderMarketInsight(data);

  const plan = data.trade_plan;
  const planItems = [
    { label: "Entry Zone", value: range(plan.entry_low, plan.entry_high, data.currency) },
    { label: "Stop Loss", value: money(plan.stop_loss, data.currency) },
    { label: "Target 1", value: money(plan.target_1, data.currency) },
    { label: "Target 2", value: money(plan.target_2, data.currency) },
    {
      label: "Risk/Reward",
      value: plan.risk_reward_ratio != null ? `1:${plan.risk_reward_ratio.toFixed(2)}` : "N/A",
    },
  ];
  document.getElementById("trade-plan").innerHTML = planItems
    .map(
      (item) => `
      <div class="trade-item">
        <span class="trade-label">${item.label}</span>
        <span class="trade-value">${item.value}</span>
      </div>`
    )
    .join("");

  const strategiesEl = document.getElementById("strategies");
  strategiesEl.innerHTML = (data.market_strategies || [])
    .map(
      (s) => `
      <div class="strategy-card suitability-${s.suitability}">
        <div class="strategy-header">
          <span class="strategy-title">${s.title}</span>
          <span class="suitability-tag ${s.suitability}">${s.suitability}</span>
        </div>
        <p class="strategy-desc">${s.description}</p>
        <p class="strategy-rationale">${s.rationale}</p>
      </div>`
    )
    .join("");

  const metrics = [
    ["52W High", fmt(data.fifty_two_week_high)],
    ["52W Low", fmt(data.fifty_two_week_low)],
    ["SMA 20", fmt(data.indicators.sma_20)],
    ["SMA 50", fmt(data.indicators.sma_50)],
    ["SMA 200", fmt(data.indicators.sma_200)],
    ["RSI (14)", fmt(data.indicators.rsi_14)],
    ["MACD", fmt(data.indicators.macd)],
    ["MACD Signal", fmt(data.indicators.macd_signal)],
    ["Volume Ratio", fmt(data.indicators.volume_ratio, "x")],
    ["1M Return", fmt(data.indicators.return_1m_pct, "%")],
    ["3M Return", fmt(data.indicators.return_3m_pct, "%")],
    ["From 52W High", fmt(data.indicators.pct_from_52w_high, "%")],
    ["From 52W Low", fmt(data.indicators.pct_from_52w_low, "%")],
  ];
  document.querySelector("#metrics-table tbody").innerHTML = metrics
    .map(([label, value]) => `<tr><td>${label}</td><td class="num">${value}</td></tr>`)
    .join("");

  document.getElementById("risks-list").innerHTML = (data.risks || [])
    .map((risk) => `<li>${risk}</li>`)
    .join("");

  document.querySelector("#breakdown-table tbody").innerHTML = (data.signal_details || [])
    .map(
      (d) => `
      <tr>
        <td>${d.factor}</td>
        <td class="num">${d.score}</td>
        <td class="num">${d.weight}</td>
        <td>${d.note}</td>
      </tr>`
    )
    .join("");

  document.querySelector("#sessions-table tbody").innerHTML = (data.recent_bars || [])
    .map(
      (bar) => `
      <tr>
        <td>${bar.date}</td>
        <td class="num">${fmt(bar.open)}</td>
        <td class="num">${fmt(bar.high)}</td>
        <td class="num">${fmt(bar.low)}</td>
        <td class="num">${fmt(bar.close)}</td>
        <td class="num">${fmt(bar.volume)}</td>
      </tr>`
    )
    .join("");

  renderChart(data.chart_data, data.chart_data?.chart_range_label);
  setChartContext(data);
  setActiveChartRange(data.chart_data?.chart_range || "6m");
  activeChartInterval = data.chart_data?.interval || "1d";
  updateIntervalTabs(
    data.chart_data?.chart_range || "6m",
    activeChartInterval,
    data.chart_data?.available_intervals
  );
  renderBeginnerGuide(data.beginner_guide, activeBeginnerLang);
}

let currentChartContext = null;
let currentChartData = null;
let activeChartRange = "6m";
let activeChartInterval = "1d";
let activeChartType = "line";

function setChartContext(data) {
  const plan = data.trade_plan || {};
  currentChartContext = {
    symbol: data.symbol?.input,
    market_type: data.market_type,
    levels: data.chart_data?.levels || {},
    plan,
  };
}

function setActiveChartRange(range) {
  activeChartRange = range;
  document.querySelectorAll(".chart-range-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.range === range);
  });
}

function setActiveChartInterval(interval) {
  activeChartInterval = interval;
  document.querySelectorAll(".chart-interval-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.interval === interval);
  });
}

function setActiveChartType(type) {
  activeChartType = type;
  document.querySelectorAll(".chart-type-tab").forEach((tab) => {
    tab.classList.toggle("active", tab.dataset.type === type);
  });
}

function updateIntervalTabs(chartRange, selectedInterval, availableIntervals) {
  const container = document.getElementById("chart-interval-tabs");
  if (!container) return;

  const options = availableIntervals || [];
  container.innerHTML = options
    .map(
      (opt) =>
        `<button type="button" class="chart-interval-tab${opt.key === selectedInterval ? " active" : ""}" data-interval="${opt.key}" role="tab">${opt.label}</button>`
    )
    .join("");

  container.querySelectorAll(".chart-interval-tab").forEach((tab) => {
    tab.addEventListener("click", async () => {
      if (!currentChartContext || tab.dataset.interval === activeChartInterval) return;
      activeChartInterval = tab.dataset.interval;
      setActiveChartInterval(activeChartInterval);
      await loadChart(activeChartRange, activeChartInterval);
    });
  });
}

function updateChartHint(chart, rangeLabel) {
  const hintEl = document.getElementById("chart-hint");
  if (!hintEl || !chart) return;
  const intervalLabel = chart.interval_label || chart.interval || "1d";
  const styleLabel = activeChartType === "candle" ? "Candlesticks" : "Line + SMA 20/50";
  hintEl.textContent = `${styleLabel} · ${rangeLabel || chart.chart_range_label} · ${intervalLabel} bars`;
}

document.querySelectorAll(".chart-range-tab").forEach((tab) => {
  tab.addEventListener("click", async () => {
    if (!currentChartContext || tab.dataset.range === activeChartRange) return;
    await loadChart(tab.dataset.range, null);
  });
});

document.querySelectorAll(".chart-type-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    if (tab.dataset.type === activeChartType) return;
    setActiveChartType(tab.dataset.type);
    if (currentChartData) {
      renderChart(currentChartData, currentChartData.chart_range_label);
    }
  });
});

async function loadChart(range, interval = activeChartInterval) {
  if (!currentChartContext) return;

  const chartEl = document.getElementById("price-chart");
  const hintEl = document.getElementById("chart-hint");
  setActiveChartRange(range);
  chartEl.innerHTML = "<p class=\"chart-loading\">Loading chart…</p>";
  if (hintEl) hintEl.textContent = "Fetching price history…";

  const params = new URLSearchParams({
    symbol: currentChartContext.symbol,
    market_type: currentChartContext.market_type,
    chart_range: range,
  });
  if (interval) params.set("interval", interval);

  const plan = currentChartContext.plan;
  if (plan.entry_low != null) params.set("entry_low", plan.entry_low);
  if (plan.entry_high != null) params.set("entry_high", plan.entry_high);
  if (plan.stop_loss != null) params.set("stop_loss", plan.stop_loss);
  if (plan.target_1 != null) params.set("target_1", plan.target_1);
  if (plan.target_2 != null) params.set("target_2", plan.target_2);

  try {
    const { data: chartData, ok } = await apiFetch(`/api/chart?${params}`);
    if (!ok) {
      throw new Error(formatApiError(chartData, "Failed to load chart"));
    }
    activeChartInterval = chartData.interval || activeChartInterval;
    updateIntervalTabs(chartData.chart_range, activeChartInterval, chartData.available_intervals);
    renderChart(chartData, chartData.chart_range_label);
  } catch (err) {
    chartEl.innerHTML = `<p class="chart-empty">${err.message}</p>`;
    if (hintEl) hintEl.textContent = "Could not load chart for this range.";
  }
}

function renderChart(chart, rangeLabel = "6 Months") {
  currentChartData = chart;
  if (activeChartType === "candle") {
    renderCandlestickChart(chart, rangeLabel);
  } else {
    renderLineChart(chart, rangeLabel);
  }
  updateChartHint(chart, rangeLabel);
}

function fmtCompact(value) {
  const n = Number(value);
  if (Number.isNaN(n)) return "";
  if (n >= 10000) return `${(n / 1000).toFixed(0)}k`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n < 100 ? n.toFixed(2) : n.toFixed(0);
}

function computeChartScale(series, levels, useOhlc = false) {
  const priceValues = [];
  series.forEach((p) => {
    if (useOhlc) {
      priceValues.push(p.high, p.low);
    } else {
      if (p.close != null) priceValues.push(p.close);
    }
    if (p.sma_20 != null) priceValues.push(p.sma_20);
    if (p.sma_50 != null) priceValues.push(p.sma_50);
  });

  const closes = series.map((p) => p.close).filter((v) => v != null);
  let ymin = Math.min(...priceValues);
  let ymax = Math.max(...priceValues);
  const lastClose = closes[closes.length - 1] ?? ymax;
  const minSpan = Math.max(lastClose * 0.004, 1);
  if (ymax - ymin < minSpan) {
    const mid = (ymax + ymin) / 2;
    ymin = mid - minSpan / 2;
    ymax = mid + minSpan / 2;
  }
  const padY = (ymax - ymin) * 0.12 || lastClose * 0.02 || 1;
  ymin -= padY;
  ymax += padY;
  const ySpan = ymax - ymin || 1;

  return { ymin, ymax, ySpan, lastClose, closes };
}

function buildChartSvgParts(series, levels, layout, options = {}) {
  const { showSma = true, showLevels = true, candlesticks = false } = options;
  const W = layout.W;
  const H = layout.H;
  const pad = layout.pad;
  const plotW = layout.plotW;
  const plotH = layout.plotH;
  const ymin = layout.ymin;
  const ymax = layout.ymax;
  const ySpan = layout.ySpan;

  const xAt = (i) => pad.l + (i / (series.length - 1 || 1)) * plotW;
  const yAt = (v) => pad.t + plotH - ((v - ymin) / ySpan) * plotH;

  const levelLine = (value, color, label) => {
    if (!showLevels || value == null) return "";
    let y = yAt(value);
    let textY = y - 4;
    let displayLabel = label;
    if (value > ymax) {
      y = pad.t + 1;
      textY = pad.t + 11;
      displayLabel = `${label} ↑`;
    } else if (value < ymin) {
      y = pad.t + plotH - 1;
      textY = pad.t + plotH - 4;
      displayLabel = `${label} ↓`;
    }
    return `
      <line x1="${pad.l}" y1="${y}" x2="${W - pad.r}" y2="${y}"
        stroke="${color}" stroke-width="1" stroke-dasharray="5,4" opacity="0.8" />
      <text x="${W - pad.r}" y="${textY}" fill="${color}" font-size="10" text-anchor="end">${displayLabel}</text>`;
  };

  let entryBand = "";
  if (showLevels && levels.entry_low != null && levels.entry_high != null) {
    const visibleHigh = Math.min(levels.entry_high, ymax);
    const visibleLow = Math.max(levels.entry_low, ymin);
    if (visibleHigh > visibleLow) {
      const yTop = yAt(visibleHigh);
      const yBottom = yAt(visibleLow);
      entryBand = `<rect x="${pad.l}" y="${yTop}" width="${plotW}" height="${yBottom - yTop}" fill="rgba(59,130,246,0.14)" />`;
    }
  }

  const gridLines = [0, 0.25, 0.5, 0.75, 1]
    .map((t) => {
      const v = ymin + ySpan * (1 - t);
      const y = pad.t + plotH * t;
      return `
        <line x1="${pad.l}" y1="${y}" x2="${W - pad.r}" y2="${y}" stroke="#2d3a4f" stroke-width="1" />
        <text x="${pad.l - 6}" y="${y + 4}" fill="#8b9cb3" font-size="10" text-anchor="end">${fmtCompact(v)}</text>`;
    })
    .join("");

  const xLabelIndexes = [0, Math.floor(series.length / 2), series.length - 1];
  const formatAxisLabel = (dateStr) => {
    if (dateStr.includes(" ")) {
      const [datePart, timePart] = dateStr.split(" ");
      if (series.length <= 40) return timePart.slice(0, 5);
      return `${datePart.slice(5)} ${timePart.slice(0, 5)}`;
    }
    return dateStr.slice(5);
  };
  const xLabels = xLabelIndexes
    .map(
      (i) =>
        `<text x="${xAt(i)}" y="${H - 8}" fill="#8b9cb3" font-size="10" text-anchor="middle">${formatAxisLabel(series[i].date)}</text>`
    )
    .join("");

  const linePath = (key) => {
    let started = false;
    let d = "";
    series.forEach((p, i) => {
      const v = p[key];
      if (v == null) {
        started = false;
        return;
      }
      d += `${started ? "L" : "M"}${xAt(i).toFixed(1)},${yAt(v).toFixed(1)} `;
      started = true;
    });
    return d.trim();
  };

  const slotW = plotW / Math.max(series.length, 1);
  const bodyW = Math.max(2, Math.min(10, slotW * 0.65));
  const candles = candlesticks
    ? series
        .map((p, i) => {
          const cx = xAt(i);
          const open = p.open ?? p.close;
          const close = p.close;
          const high = p.high ?? close;
          const low = p.low ?? close;
          const bullish = close >= open;
          const color = bullish ? "#22c55e" : "#ef4444";
          const yHigh = yAt(high);
          const yLow = yAt(low);
          const yOpen = yAt(open);
          const yClose = yAt(close);
          const bodyTop = Math.min(yOpen, yClose);
          const bodyHeight = Math.max(1, Math.abs(yClose - yOpen));
          return `
            <line x1="${cx}" y1="${yHigh}" x2="${cx}" y2="${yLow}" stroke="${color}" stroke-width="1" />
            <rect x="${(cx - bodyW / 2).toFixed(1)}" y="${bodyTop.toFixed(1)}" width="${bodyW.toFixed(1)}" height="${bodyHeight.toFixed(1)}" fill="${color}" />
          `;
        })
        .join("")
    : "";

  const smaLayers = showSma
    ? `
      <path d="${linePath("sma_50")}" fill="none" stroke="#eab308" stroke-width="1.5" opacity="0.75" />
      <path d="${linePath("sma_20")}" fill="none" stroke="#60a5fa" stroke-width="1.5" opacity="0.85" />`
    : "";

  const closeLine = !candlesticks
    ? `<path d="${linePath("close")}" fill="none" stroke="#e8edf4" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />`
    : "";

  const last = series[series.length - 1];
  const lastMarker =
    !candlesticks && last
      ? `<circle cx="${xAt(series.length - 1)}" cy="${yAt(last.close)}" r="3.5" fill="#3b82f6" />`
      : "";

  return {
    svgBody: `
      ${gridLines}
      ${entryBand}
      ${levelLine(levels.stop_loss, "#ef4444", "Stop")}
      ${levelLine(levels.target_1, "#22c55e", "T1")}
      ${levelLine(levels.target_2, "#22c55e", "T2")}
      ${smaLayers}
      ${candles}
      ${closeLine}
      ${xLabels}
      ${lastMarker}`,
    xAt,
    yAt,
  };
}

function renderLineChart(chart, rangeLabel = "6 Months") {
  const wrap = document.getElementById("price-chart");
  const legend = document.getElementById("price-chart-legend");

  if (!wrap) return;

  if (!chart?.series?.length) {
    wrap.innerHTML = "<p class=\"chart-empty\">Chart data not available.</p>";
    if (legend) legend.innerHTML = "";
    return;
  }

  const series = chart.series;
  const levels = chart.levels || {};
  const W = 800;
  const H = 260;
  const pad = { t: 18, r: 16, b: 36, l: 56 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const scale = computeChartScale(series, levels, false);
  const layout = { W, H, pad, plotW, plotH, ...scale };
  const { svgBody } = buildChartSvgParts(series, levels, layout, {
    showSma: true,
    showLevels: true,
    candlesticks: false,
  });

  wrap.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="price-chart-svg" role="img" aria-label="Price line chart">
      ${svgBody}
    </svg>`;

  if (legend) {
    legend.innerHTML = `
      <span class="legend-item"><span class="legend-dot close"></span>Close</span>
      <span class="legend-item"><span class="legend-dot sma20"></span>SMA 20</span>
      <span class="legend-item"><span class="legend-dot sma50"></span>SMA 50</span>
      ${levels.entry_low != null ? "<span class=\"legend-item\"><span class=\"legend-dot entry\"></span>Entry zone</span>" : ""}
      ${levels.stop_loss != null ? "<span class=\"legend-item\"><span class=\"legend-dot stop\"></span>Stop-loss</span>" : ""}
      ${levels.target_1 != null ? "<span class=\"legend-item\"><span class=\"legend-dot target\"></span>Targets</span>" : ""}`;
  }
}

function renderCandlestickChart(chart, rangeLabel = "6 Months") {
  const wrap = document.getElementById("price-chart");
  const legend = document.getElementById("price-chart-legend");

  if (!wrap) return;

  if (!chart?.series?.length) {
    wrap.innerHTML = "<p class=\"chart-empty\">Chart data not available.</p>";
    if (legend) legend.innerHTML = "";
    return;
  }

  const series = chart.series;
  const levels = chart.levels || {};
  const W = 800;
  const H = 260;
  const pad = { t: 18, r: 16, b: 36, l: 56 };
  const plotW = W - pad.l - pad.r;
  const plotH = H - pad.t - pad.b;
  const scale = computeChartScale(series, levels, true);
  const layout = { W, H, pad, plotW, plotH, ...scale };
  const { svgBody } = buildChartSvgParts(series, levels, layout, {
    showSma: false,
    showLevels: true,
    candlesticks: true,
  });

  wrap.innerHTML = `
    <svg viewBox="0 0 ${W} ${H}" class="price-chart-svg" role="img" aria-label="Candlestick chart">
      ${svgBody}
    </svg>`;

  if (legend) {
    legend.innerHTML = `
      <span class="legend-item"><span class="legend-dot bullish"></span>Bullish</span>
      <span class="legend-item"><span class="legend-dot bearish"></span>Bearish</span>
      ${levels.entry_low != null ? "<span class=\"legend-item\"><span class=\"legend-dot entry\"></span>Entry zone</span>" : ""}
      ${levels.stop_loss != null ? "<span class=\"legend-item\"><span class=\"legend-dot stop\"></span>Stop-loss</span>" : ""}
      ${levels.target_1 != null ? "<span class=\"legend-item\"><span class=\"legend-dot target\"></span>Targets</span>" : ""}`;
  }
}

function renderPriceChart(chart, rangeLabel = "6 Months") {
  renderChart(chart, rangeLabel);
}

let currentBeginnerGuide = null;
let activeBeginnerLang = "english";

document.querySelectorAll(".beginner-lang-tabs .lang-tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".beginner-lang-tabs .lang-tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    activeBeginnerLang = tab.dataset.lang;
    if (currentBeginnerGuide) {
      renderBeginnerGuide(currentBeginnerGuide, activeBeginnerLang);
    }
  });
});

function renderBeginnerGuide(guide, lang = "english") {
  const section = document.getElementById("beginner-guide-section");
  if (!guide) {
    section.classList.add("hidden");
    return;
  }
  section.classList.remove("hidden");
  currentBeginnerGuide = guide;

  const content = guide[lang] || guide.english || guide;
  if (!content) return;

  document.getElementById("beginner-disclaimer").textContent = content.disclaimer || "";

  const verdict = content.verdict || {};
  document.getElementById("beginner-verdict-headline").textContent = verdict.headline || "";
  document.getElementById("beginner-verdict-summary").textContent = verdict.simple_summary || "";

  document.getElementById("beginner-why-yes").innerHTML = (content.why_yes || [])
    .map((item) => `<li>${item}</li>`)
    .join("");
  document.getElementById("beginner-why-no").innerHTML = (content.why_no || [])
    .map((item) => `<li>${item}</li>`)
    .join("");

  document.getElementById("beginner-checklist").innerHTML = (content.checklist || [])
    .map(
      (item) => `
      <div class="checklist-item status-${item.status}">
        <span class="checklist-icon">${checklistIcon(item.status)}</span>
        <div>
          <strong>${item.item}</strong>
          <p>${item.detail}</p>
        </div>
      </div>`
    )
    .join("");

  const signal = content.signal_explained || {};
  document.getElementById("beginner-signal-explained").innerHTML = `
    <p><strong>${(signal.signal || "").replace(/_/g, " ")}</strong> — ${signal.what_it_means || ""}</p>
    ${signal.for_this_symbol ? `<p>${signal.for_this_symbol}</p>` : ""}`;

  document.getElementById("beginner-analysis-plain").textContent =
    content.analysis_in_plain_terms || "";

  const levels = content.key_levels_explained || {};
  document.getElementById("beginner-key-levels").innerHTML = [
    levels.entry_zone,
    levels.stop_loss,
    levels.targets,
    levels.support_resistance,
    levels.risk_reward,
  ]
    .filter(Boolean)
    .map((line) => `<p>${line}</p>`)
    .join("");

  document.getElementById("beginner-risks").innerHTML = (content.risks_plain || [])
    .map((risk) => `<li>${risk}</li>`)
    .join("");

  document.getElementById("beginner-next-steps").innerHTML = (content.next_steps || [])
    .map(
      (step) => `
      <li>
        <strong>${step.action}</strong>
        <span class="step-detail">${step.detail}</span>
      </li>`
    )
    .join("");

  document.getElementById("beginner-glossary").innerHTML = (content.glossary_snippets || [])
    .map(
      (entry) => `
      <div class="glossary-entry">
        <dt>${entry.term}</dt>
        <dd>${entry.explanation}</dd>
      </div>`
    )
    .join("");
}

function checklistIcon(status) {
  const icons = { pass: "✓", warn: "!", fail: "✗", neutral: "○" };
  return icons[status] || "○";
}

const beginnerToggle = document.getElementById("beginner-guide-toggle");
const beginnerBody = document.getElementById("beginner-guide-body");
const beginnerChevron = document.getElementById("beginner-chevron");

beginnerToggle.addEventListener("click", () => {
  const expanded = beginnerToggle.getAttribute("aria-expanded") === "true";
  beginnerToggle.setAttribute("aria-expanded", String(!expanded));
  beginnerBody.classList.toggle("collapsed", expanded);
  beginnerChevron.textContent = expanded ? "▶" : "▼";
});

function renderMarketInsight(data) {
  const insight = data.market_insight || {};
  document.getElementById("insight-thesis").textContent = insight.thesis || "No insight available.";
  document.getElementById("insight-providers").textContent = insight.provider_summary || "";

  const gridItems = [
    ["Regime", insight.regime || "N/A"],
    ["Trend Strength", insight.trend_strength != null ? `${insight.trend_strength}%` : "N/A"],
    ["Support", fmt(insight.support_level)],
    ["Resistance", fmt(insight.resistance_level)],
    ["ATR %", fmt(insight.atr_pct, "%")],
    [
      "Data Providers",
      (data.data_providers || []).join(", ") || "N/A",
    ],
    [
      "Price Agreement",
      data.quote_agreement_pct != null ? `${data.quote_agreement_pct}%` : "N/A",
    ],
  ];

  document.getElementById("insight-grid").innerHTML = gridItems
    .map(
      ([label, value]) => `
      <div class="insight-item">
        <span class="insight-label">${label}</span>
        <span class="insight-value">${value}</span>
      </div>`
    )
    .join("");

  const fundamentals = insight.fundamentals || {};
  const fundItems = Object.entries(fundamentals);
  document.getElementById("insight-fundamentals").innerHTML = fundItems.length
    ? `<h4>Fundamentals</h4><div class="fund-grid">${fundItems
        .map(
          ([key, value]) => `
          <div class="fund-item">
            <span>${key.replace(/_/g, " ")}</span>
            <strong>${typeof value === "number" ? fmt(value) : value}</strong>
          </div>`
        )
        .join("")}</div>`
    : "";
}

async function checkServerOnLoad() {
  const { ok } = await apiFetch("/api/ping", { cache: "no-store" });
  if (!ok) {
    showError(
      "Server is waking up or temporarily unavailable. Wait 30 seconds, then try analyzing a symbol."
    );
  }
}

checkServerOnLoad();
