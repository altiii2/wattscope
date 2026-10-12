(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  const state = { overview: null, clients: [], forecast: null, requestId: 0, hoverIndex: null };
  const SVG_NS = "http://www.w3.org/2000/svg";
  const finite = (value) => value !== null && value !== undefined && value !== "" && Number.isFinite(Number(value)) ? Number(value) : null;
  const format = (value, digits = 1) => finite(value) === null ? "—" : Number(value).toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: digits });
  const time = (value) => {
    const text = String(value || "").replace(" ", "T");
    return Date.parse(/(?:Z|[+-]\d{2}:\d{2})$/i.test(text) ? text : text + "Z");
  };
  const dateLabel = (value, options) => {
    const stamp = time(value);
    return Number.isFinite(stamp) ? new Intl.DateTimeFormat("en-GB", { timeZone: "UTC", ...options }).format(stamp) : "—";
  };
  const shortDate = (value) => dateLabel(value, { day: "2-digit", month: "short" });
  const fullDate = (value) => dateLabel(value, { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });
  const text = (id, value) => { $(id).textContent = value; };
  const node = (tag, content, className) => {
    const element = document.createElement(tag);
    if (content !== undefined) element.textContent = content;
    if (className) element.className = className;
    return element;
  };
  function metric(id, value, suffix, digits = 1) {
    const element = $(id);
    element.replaceChildren(document.createTextNode(format(value, digits)));
    if (finite(value) !== null && suffix) element.appendChild(node("small", suffix));
  }
  function status(message, mode = "") {
    $("forecast-status").className = "status-pill" + (mode ? " is-" + mode : "");
    $("forecast-status").replaceChildren(document.createElement("span"), document.createTextNode(message));
  }
  function error(message) {
    $("error-message").hidden = !message;
    $("error-message").textContent = message || "";
  }
  async function api(path, options = {}) {
    const response = await fetch(path, { ...options, headers: { "Accept": "application/json", ...(options.headers || {}) } });
    let body;
    try { body = await response.json(); } catch (_) { throw new Error("The server returned an unreadable response."); }
    if (!response.ok) {
      let detail = body.detail;
      if (Array.isArray(detail)) detail = detail.map((item) => item.msg || "Invalid request").join("; ");
      throw new Error(typeof detail === "string" ? detail : "The request could not be completed (" + response.status + ").");
    }
    return body;
  }
  function renderOverview() {
    const overview = state.overview || {};
    const data = overview.data || {};
    const model = overview.model || {};
    const validation = overview.validation || {};
    const metrics = overview.metrics || {};
    if (data.test_start) $("origin-input").min = String(data.test_start).slice(0, 10) + "T00:00";
    if (data.end) $("origin-input").max = String(data.end).slice(0, 16);
    metric("wape-value", metrics.model?.wape, "%", 1);
    metric("coverage-value", finite(model.interval_coverage) === null ? null : model.interval_coverage * 100, "%", 1);
    const modelWape = finite(metrics.model?.wape);
    const dailyWape = finite(metrics.previous_day?.wape);
    const improvement = modelWape !== null && dailyWape !== null && dailyWape > 0 ? (dailyWape - modelWape) / dailyWape * 100 : null;
    $("improvement-context").classList.toggle("positive", improvement !== null && improvement > 0);
    text("improvement-context", improvement === null ? "Model error across the test set" : format(Math.abs(improvement), 1) + "% " + (improvement >= 0 ? "lower" : "higher") + " WAPE than the daily baseline");
    text("dataset-name", data.source || "Public electricity dataset");
    text("client-count", String(data.clients ?? state.clients.length) + " · hourly " + (data.unit || "kWh"));
    text("evaluation-protocol", validation.strategy || "Chronological holdout evaluation");
    const body = $("metrics-body");
    body.replaceChildren();
    [
      ["model", model.name || "Forecast model"],
      ["previous_day", "Previous day"],
      ["previous_week", "Previous week"],
    ].forEach(([key, label]) => {
      const row = node("tr");
      if (key === "model") row.className = "model-row";
      const nameCell = node("td");
      nameCell.append(node("span", "", "method-dot"), document.createTextNode(label));
      row.appendChild(nameCell);
      const values = metrics[key] || {};
      ["mae", "rmse", "wape"].forEach((metricName) => row.appendChild(node("td", format(values[metricName], 2) + (metricName === "wape" && finite(values[metricName]) !== null ? "%" : ""))));
      body.appendChild(row);
    });
    const splits = $("split-details");
    splits.replaceChildren();
    [["train", "Train"], ["validation", "Validate"], ["calibration", "Calibrate"], ["test", "Test"]].forEach(([key, label]) => {
      const item = node("div");
      const splitDate = (value) => dateLabel(value, { day: "2-digit", month: "short", year: "numeric" });
      item.append(node("strong", label), node("span", splitDate(data[key + "_start"]) + " – " + splitDate(data[key + "_end"])));
      splits.appendChild(item);
      const duration = time(data[key + "_end"]) - time(data[key + "_start"]) + 3600000;
      const segment = document.querySelector(".split-" + key);
      if (segment && Number.isFinite(duration) && duration > 0) segment.style.flex = String(duration / 3600000);
    });
    const features = $("feature-list");
    features.replaceChildren();
    (Array.isArray(model.features) ? model.features : []).forEach((feature) => features.appendChild(node("span", String(feature), "feature-chip")));
    const notes = $("study-note-list");
    notes.replaceChildren();
    (Array.isArray(overview.notes) ? overview.notes : []).forEach((note) => notes.appendChild(node("li", String(note))));
  }
  function populateClients() {
    const select = $("client-select");
    select.replaceChildren();
    state.clients.forEach((client) => {
      const id = String(client.client_id ?? client.id ?? "");
      if (!id) return;
      const option = node("option", client.label || client.name || id);
      option.value = id;
      select.appendChild(option);
    });
    const defaultClient = state.overview?.client_id_default;
    if (defaultClient && [...select.options].some((option) => option.value === defaultClient)) select.value = defaultClient;
    select.disabled = !select.options.length;
    $("reset-button").disabled = !select.options.length;
    $("forecast-button").disabled = !select.options.length;
    if (!select.options.length) throw new Error("No customer meters are available in the prepared dataset.");
  }
  function renderForecast() {
    const forecast = state.forecast;
    const predictions = (forecast.forecast || []).map((point) => finite(point.prediction)).filter((value) => value !== null);
    metric("energy-value", predictions.length ? predictions.reduce((sum, value) => sum + value, 0) : null, forecast.unit || "kWh", 0);
    const peak = (forecast.forecast || []).reduce((best, point) => finite(point.prediction) !== null && (!best || point.prediction > best.prediction) ? point : best, null);
    metric("peak-value", peak?.prediction, forecast.unit || "kWh", 1);
    text("peak-context", peak ? fullDate(peak.timestamp) + " · dataset time" : "Highest predicted hour");
    const points = forecast.forecast || [];
    text("forecast-subtitle", forecast.client_id + " · " + (points.length ? shortDate(points[0].timestamp) + " – " + shortDate(points.at(-1).timestamp) : "No forecast timestamps") + " · " + points.length + "-hour horizon");
    text("model-name", forecast.model_name || state.overview?.model?.name || "Forecast model");
    text("interval-note", forecast.interval_note || state.overview?.model?.interval_note || "Empirical intervals, not a guarantee.");
    if (forecast.origin) $("origin-input").value = String(forecast.origin).replace(" ", "T").slice(0, 16);
    validateOrigin();
    $("actual-legend").hidden = !points.some((point) => finite(point.actual) !== null);
    $("download-button").disabled = false;
    status("Benchmark ready");
    drawChart();
  }
  function svgNode(tag, attrs = {}, content) {
    const element = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (content !== undefined) element.textContent = content;
    return element;
  }
  function drawChart() {
    const svg = $("forecast-chart");
    const wrap = $("chart-wrap");
    const forecast = state.forecast;
    if (!forecast) return;
    const history = (forecast.history || []).filter((point) => Number.isFinite(time(point.timestamp)));
    const future = (forecast.forecast || []).filter((point) => Number.isFinite(time(point.timestamp)));
    const points = history.map((point) => ({ ...point, kind: "history" })).concat(future.map((point) => ({ ...point, kind: "forecast" })));
    const width = Math.max(320, wrap.clientWidth - (window.innerWidth <= 620 ? 4 : 28));
    const height = wrap.clientHeight;
    const margin = { left: width < 500 ? 49 : 66, right: 24, top: 30, bottom: 49 };
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    svg.replaceChildren(svgNode("title", { id: "chart-title" }, "Electricity load forecast for " + forecast.client_id), svgNode("desc", { id: "chart-description" }, "Historical hourly electricity followed by model forecasts, prediction intervals, holdout actuals when available, and an optional daily baseline. Values are in " + (forecast.unit || "kWh") + "."));
    svg.setAttribute("viewBox", "0 0 " + width + " " + height);
    svg.setAttribute("tabindex", "0");
    $("chart-empty").hidden = points.length > 0;
    wrap.setAttribute("aria-busy", "false");
    if (!points.length) {
      $("chart-empty").replaceChildren(node("span", "No observations are available for this window."));
      return;
    }
    const baseline = $("baseline-toggle").checked;
    const allValues = points.flatMap((point) => point.kind === "history" ? [finite(point.actual)] : [finite(point.prediction), finite(point.lower), finite(point.upper), finite(point.actual), ...(baseline ? [finite(point.previous_day)] : [])]).filter((value) => value !== null);
    const yMin = Math.min(0, ...allValues);
    const yMax = Math.max(1, ...allValues) * 1.12;
    const firstTime = Math.min(...points.map((point) => time(point.timestamp)));
    const lastTime = Math.max(...points.map((point) => time(point.timestamp)));
    const timeRange = Math.max(3600000, lastTime - firstTime);
    const x = (timestamp) => margin.left + (time(timestamp) - firstTime) / timeRange * plotWidth;
    const y = (value) => margin.top + plotHeight - (value - yMin) / (yMax - yMin) * plotHeight;
    const font = { "font-family": "Inter, Segoe UI, Arial, sans-serif", "font-size": width < 500 ? 8 : 9, fill: "#9aa8bc" };
    const originTime = time(forecast.origin);
    const originX = Number.isFinite(originTime) ? Math.min(margin.left + plotWidth, Math.max(margin.left, x(forecast.origin))) : future.length ? x(future[0].timestamp) : margin.left + plotWidth;
    svg.appendChild(svgNode("rect", { x: originX, y: margin.top, width: Math.max(0, width - margin.right - originX), height: plotHeight, fill: "#f8faff" }));
    svg.appendChild(svgNode("text", { x: margin.left, y: 16, ...font, "font-size": 8, fill: "#96a5ba" }, forecast.unit || "kWh"));
    for (let tick = 0; tick <= 4; tick++) {
      const value = yMin + (yMax - yMin) * tick / 4;
      const yy = y(value);
      svg.append(svgNode("line", { x1: margin.left, y1: yy, x2: width - margin.right, y2: yy, stroke: "#eaf0f7", "stroke-width": 1, "stroke-dasharray": "3 4" }), svgNode("text", { x: margin.left - 11, y: yy + 3, "text-anchor": "end", ...font }, format(value, Math.abs(yMax) < 10 ? 1 : 0)));
    }
    const tickCount = width < 500 ? 4 : 6;
    for (let tick = 0; tick < tickCount; tick++) {
      const stamp = firstTime + timeRange * tick / (tickCount - 1);
      const xx = margin.left + plotWidth * tick / (tickCount - 1);
      const iso = new Date(stamp).toISOString();
      svg.appendChild(svgNode("text", { x: xx, y: height - 24, "text-anchor": tick === 0 ? "start" : tick === tickCount - 1 ? "end" : "middle", ...font }, dateLabel(iso, { day: "2-digit", month: "short", hour: "2-digit", hourCycle: "h23" })));
    }
    svg.append(svgNode("line", { x1: originX, y1: margin.top, x2: originX, y2: margin.top + plotHeight, stroke: "#c0d0ef", "stroke-dasharray": "4 4" }), svgNode("text", { x: Math.min(width - 80, originX + 8), y: margin.top + 13, ...font, "font-size": 8, fill: "#86a0d1" }, "FORECAST"));
    const intervalPoints = future.filter((point) => finite(point.lower) !== null && finite(point.upper) !== null);
    if (intervalPoints.length) {
      const upper = intervalPoints.map((point) => x(point.timestamp) + "," + y(point.upper));
      const lower = [...intervalPoints].reverse().map((point) => x(point.timestamp) + "," + y(point.lower));
      svg.appendChild(svgNode("polygon", { points: upper.concat(lower).join(" "), fill: "#e4edff", opacity: ".9" }));
    }
    function line(series, key, color, strokeWidth, dash) {
      let path = "";
      let active = false;
      series.forEach((point) => {
        const value = finite(point[key]);
        if (value === null) { active = false; return; }
        path += (active ? " L" : " M") + x(point.timestamp).toFixed(2) + " " + y(value).toFixed(2);
        active = true;
      });
      if (path) svg.appendChild(svgNode("path", { d: path, fill: "none", stroke: color, "stroke-width": strokeWidth, "stroke-linejoin": "round", "stroke-linecap": "round", ...(dash ? { "stroke-dasharray": dash } : {}) }));
    }
    line(history, "actual", "#708198", 1.9);
    if (baseline) line(future, "previous_day", "#a9b6cc", 1.4, "4 4");
    line(future, "actual", "#27968a", 1.8, "3 3");
    line(future, "prediction", "#3b63f1", 2.5);
    const hoverLine = svgNode("line", { x1: 0, y1: margin.top, x2: 0, y2: margin.top + plotHeight, stroke: "#90a6d2", "stroke-width": 1, visibility: "hidden" });
    const hoverDot = svgNode("circle", { r: 4, fill: "#3b63f1", stroke: "white", "stroke-width": 2, visibility: "hidden" });
    svg.append(hoverLine, hoverDot);
    function hideTooltip() {
      $("chart-tooltip").hidden = true;
      hoverLine.setAttribute("visibility", "hidden");
      hoverDot.setAttribute("visibility", "hidden");
      state.hoverIndex = null;
    }
    function showTooltip(index) {
      const point = points[Math.min(points.length - 1, Math.max(0, index))];
      state.hoverIndex = index;
      const xx = x(point.timestamp);
      hoverLine.setAttribute("x1", xx);
      hoverLine.setAttribute("x2", xx);
      hoverLine.setAttribute("visibility", "visible");
      const centerValue = finite(point.kind === "history" ? point.actual : point.prediction);
      if (centerValue !== null) {
        hoverDot.setAttribute("cx", xx);
        hoverDot.setAttribute("cy", y(centerValue));
        hoverDot.setAttribute("fill", point.kind === "history" ? "#708198" : "#3b63f1");
        hoverDot.setAttribute("visibility", "visible");
      } else hoverDot.setAttribute("visibility", "hidden");
      const tooltip = $("chart-tooltip");
      tooltip.replaceChildren(node("strong", fullDate(point.timestamp)));
      const entries = point.kind === "history" ? [["Observed", point.actual]] : [["Forecast", point.prediction], ["Actual", point.actual], ...(baseline ? [["Daily baseline", point.previous_day]] : [])];
      entries.forEach(([label, value]) => {
        if (finite(value) === null) return;
        const row = node("div");
        row.append(node("span", label), node("b", format(value, 2) + " " + (forecast.unit || "kWh")));
        tooltip.appendChild(row);
      });
      if (point.kind === "forecast" && finite(point.lower) !== null && finite(point.upper) !== null) {
        const row = node("div");
        row.append(node("span", "Interval"), node("b", format(point.lower, 1) + " – " + format(point.upper, 1)));
        tooltip.appendChild(row);
      }
      tooltip.hidden = false;
      tooltip.style.top = "22px";
      tooltip.style.left = Math.max(7, Math.min(wrap.clientWidth - tooltip.offsetWidth - 7, xx + 24)) + "px";
    }
    svg.onpointermove = (event) => {
      const rectangle = svg.getBoundingClientRect();
      const target = (event.clientX - rectangle.left) * width / rectangle.width;
      let nearest = 0;
      let distance = Infinity;
      points.forEach((point, index) => {
        const candidate = Math.abs(x(point.timestamp) - target);
        if (candidate < distance) { distance = candidate; nearest = index; }
      });
      showTooltip(nearest);
    };
    svg.onpointerleave = hideTooltip;
    svg.onblur = hideTooltip;
    svg.onkeydown = (event) => {
      if (!["ArrowLeft", "ArrowRight", "Escape"].includes(event.key)) return;
      event.preventDefault();
      if (event.key === "Escape") return hideTooltip();
      const next = Math.max(0, Math.min(points.length - 1, (state.hoverIndex ?? Math.max(0, history.length - 1)) + (event.key === "ArrowRight" ? 1 : -1)));
      showTooltip(next);
    };
    hideTooltip();
  }
  async function loadForecast(origin) {
    const requestId = ++state.requestId;
    error("");
    status("Updating forecast", "loading");
    $("forecast-button").disabled = true;
    $("reset-button").disabled = true;
    $("chart-wrap").setAttribute("aria-busy", "true");
    try {
      const params = new URLSearchParams({ client_id: $("client-select").value });
      if (origin) params.set("origin", origin);
      const forecast = await api("/api/forecast?" + params);
      if (requestId !== state.requestId) return;
      state.forecast = forecast;
      renderForecast();
    } catch (exception) {
      if (requestId !== state.requestId) return;
      error(exception.message || "Unable to load the forecast.");
      status("Window unavailable", "error");
      $("chart-wrap").setAttribute("aria-busy", "false");
      if (!state.forecast) {
        $("chart-empty").replaceChildren(node("span", "Forecast data could not be loaded."));
        $("chart-empty").hidden = false;
      }
    } finally {
      if (requestId === state.requestId) {
        $("forecast-button").disabled = false;
        $("reset-button").disabled = false;
      }
    }
  }
  function validateOrigin() {
    const value = $("origin-input").value;
    const valid = !value || /T00:00(?::00)?$/.test(value);
    $("origin-input").setCustomValidity(valid ? "" : "Choose midnight (00:00) in the dataset clock.");
    return valid;
  }
  $("origin-input").addEventListener("input", validateOrigin);
  $("forecast-form").addEventListener("submit", (event) => {
    event.preventDefault();
    if (!validateOrigin()) {
      $("origin-input").reportValidity();
      return;
    }
    loadForecast($("origin-input").value || undefined);
  });
  $("reset-button").addEventListener("click", () => loadForecast(state.overview?.default_origin || undefined));
  $("baseline-toggle").addEventListener("change", drawChart);
  $("download-button").addEventListener("click", () => {
    if (!state.forecast) return;
    const blob = new Blob([JSON.stringify(state.forecast, null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "wattscope-" + String(state.forecast.client_id).replace(/[^a-zA-Z0-9_-]/g, "_") + ".json";
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  document.querySelectorAll(".nav-link").forEach((link) => link.addEventListener("click", () => {
    document.querySelectorAll(".nav-link").forEach((item) => item.classList.toggle("active", item === link));
  }));
  if (typeof ResizeObserver !== "undefined") {
    let resizeFrame;
    new ResizeObserver(() => {
      cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(drawChart);
    }).observe($("chart-wrap"));
  } else window.addEventListener("resize", drawChart);
  async function initialize() {
    status("Loading data", "loading");
    try {
      [state.overview, state.clients] = await Promise.all([api("/api/overview"), api("/api/clients")]);
      renderOverview();
      populateClients();
      await loadForecast(state.overview?.default_origin || undefined);
    } catch (exception) {
      error(exception.message || "Unable to load the dataset.");
      status("Data unavailable", "error");
      $("chart-empty").replaceChildren(node("span", "Prepared forecast artifacts are not available."));
      $("chart-wrap").setAttribute("aria-busy", "false");
      text("model-name", "Data unavailable");
    }
  }
  initialize();
})();
