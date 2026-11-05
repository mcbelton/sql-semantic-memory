/* The only chart bootstrap: fixed local code, shared by standalone and canvas. */
(() => {
  "use strict";
  const $ = (id) => document.getElementById(id);
  let state = null;
  let chart = null;
  let payload;
  let page = 0;
  let failed = false;
  let watchdog = null;
  const pageSize = 100;
  Object.defineProperty(window, "__sqlmemChartStatus", { get: () => state, configurable: false });
  Object.defineProperty(window, "__sqlmemChart", { get: () => chart, configurable: false });
  const status = (next, message) => {
    state = next;
    $("render-status").textContent = message;
  };
  const showTable = () => {
    $("table-panel").hidden = false;
    $("toggle-table").setAttribute("aria-expanded", "true");
    $("toggle-table").textContent = "Hide data table";
  };
  const fail = (next, message) => {
    failed = true;
    clearTimeout(watchdog);
    status(next, message);
    $("chart-message").textContent = message;
    $("chart-message").hidden = false;
    $("download-png").disabled = true;
    showTable();
  };
  const table = () => {
    const head = $("data-table").querySelector("thead");
    const body = $("data-table").querySelector("tbody");
    head.replaceChildren();
    body.replaceChildren();
    const headings = document.createElement("tr");
    payload.columns.forEach((column) => {
      const th = document.createElement("th");
      th.scope = "col";
      th.textContent = column.label;
      headings.append(th);
    });
    head.append(headings);
    payload.display_rows.slice(page * pageSize, (page + 1) * pageSize).forEach((row) => {
      const tr = document.createElement("tr");
      row.forEach((value) => {
        const td = document.createElement("td");
        td.textContent = value;
        tr.append(td);
      });
      body.append(tr);
    });
    const pages = Math.max(1, Math.ceil(payload.row_count / pageSize));
    $("table-page").textContent = `Page ${page + 1} of ${pages} · ${payload.row_count.toLocaleString()} rows`;
    $("table-previous").disabled = page === 0;
    $("table-next").disabled = page + 1 >= pages;
  };
  const download = (url, filename) => {
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.append(link);
    link.click();
    link.remove();
  };
  const downloadPng = (url) => {
    if (typeof url !== "string" || !url.startsWith("data:image/png;base64,iVBORw0KGgo")) {
      throw new Error("PNG export did not produce a PNG image.");
    }
    download(url, "sqlmem-chart.png");
  };
  const formatted = (value) => {
    if (payload.value_format === "date" && (typeof value === "number" ||
        (typeof value === "string" && /^\d{4}-\d{2}-\d{2}/.test(value)))) {
      const date = new Date(value);
      if (Number.isFinite(date.getTime())) return date.toLocaleDateString(undefined, {timeZone: "UTC"});
    }
    if (typeof value !== "number") return String(value ?? "—");
    const options = payload.value_format === "currency" ? {style: "currency", currency: payload.currency} :
      payload.value_format === "percent" ? {style: "percent", maximumFractionDigits: 2} :
      payload.value_format === "integer" ? {maximumFractionDigits: 0} : {maximumFractionDigits: 6};
    try { return new Intl.NumberFormat(undefined, options).format(value); }
    catch (_) { return String(value); }
  };
  const option = () => {
    const next = JSON.parse(JSON.stringify(payload.option));
    const light = document.documentElement.dataset.theme === "light";
    const ink = light ? "#344460" : "#b8c6df";
    next.textStyle = { color: ink, fontFamily: "system-ui, sans-serif" };
    if (next.legend) next.legend.textStyle = { color: ink };
    if (next.visualMap) next.visualMap.textStyle = { color: ink };
    ["xAxis", "yAxis", "xAxis3D", "yAxis3D", "zAxis3D"].forEach((key) => {
      if (next[key]) {
        next[key].nameTextStyle = { color: ink };
        next[key].axisLabel = { ...next[key].axisLabel, color: ink };
      }
    });
    if (next.radar) next.radar.axisName = { color: ink };
    // Fixed callbacks only. richText interprets braces as style syntax, not markup; neutralize those.
    const inert = (value) => String(value ?? "").replace(/[{}]/g, (c) => c === "{" ? "｛" : "｝");
    next.tooltip.formatter = (params) => {
      const point = Array.isArray(params) ? params[0] : params;
      const label = point.data?.displayName ?? point.name ?? point.seriesName ?? "";
      const value = point.value;
      return inert(label) + "\n" + inert(Array.isArray(value) ? value.map(formatted).join(" · ") : formatted(value));
    };
    next.series.forEach((series) => {
      if (["graph", "sankey"].includes(series.type)) {
        series.label = { ...series.label, formatter: (point) => inert(point.data.displayName ?? point.name) };
      }
    });
    return next;
  };
  const webgl = () => {
    try {
      const canvas = document.createElement("canvas");
      const context = canvas.getContext("webgl2") || canvas.getContext("webgl") || canvas.getContext("experimental-webgl");
      if (!context) return false;
      const extension = context.getExtension("WEBGL_lose_context");
      if (extension) extension.loseContext();
      return true;
    } catch (_) { return false; }
  };
  const mount = () => {
    if (!window.echarts) {
      fail("error", "The offline chart engine could not load. Reinstall the packaged assets; your data table is available.");
      return;
    }
    if (payload.three_d && (!payload.three_d_enabled || !webgl())) {
      fail("webgl-unavailable", payload.three_d_enabled ?
        "WebGL is unavailable. Enable browser hardware acceleration to view this 3D chart. The data table is retained." :
        "3D rendering is disabled. Enable the trusted 3D setting and regenerate this chart. The data table is retained.");
      return;
    }
    if (!payload.row_count) {
      fail("empty", "No rows to plot. Your source returned an empty result.");
      return;
    }
    try {
      $("chart").addEventListener("webglcontextlost", (event) => {
        event.preventDefault();
        fail("webgl-unavailable", "WebGL context was lost. Reload this file after enabling hardware acceleration. The data table is retained.");
      }, true);
      chart = window.echarts.init($("chart"), null, {renderer: payload.three_d ? "canvas" : payload.renderer});
      chart.on("finished", () => {
        if (failed) return;
        clearTimeout(watchdog);
        status("ready", "Ready · interactive, offline");
      });
      watchdog = setTimeout(() => fail("error", "Chart readiness timed out. Reduce the data size; the data table is retained."), 5000);
      chart.setOption(option(), {notMerge: true});
      if (window.ResizeObserver) new ResizeObserver(() => { if (!failed) chart.resize(); }).observe($("chart"));
      else window.addEventListener("resize", () => { if (!failed) chart.resize(); });
    } catch (_) {
      fail("error",
        "Chart rendering failed. Check the packaged chart assets and regenerate the file. The data table is retained.");
    }
  };
  try {
    payload = JSON.parse($("sqlmem-chart-data").textContent);
    document.documentElement.dataset.theme = payload.theme;
    document.title = payload.title + " · sqlmem";
    $("chart-title").textContent = payload.title;
    $("chart-subtitle").textContent = payload.subtitle;
    const completeness = payload.source_truncated === true ? "partial result" :
      payload.source_truncated === false ? "complete supplied result" : "completeness unknown";
    $("row-summary").textContent = `${payload.row_count.toLocaleString()} plotted rows · ${payload.chart_type} · ${completeness}`;
    $("chart").setAttribute("aria-label", payload.title + ". " + $("row-summary").textContent + ". Accessible values in data table.");
    payload.warnings.forEach((warning) => {
      const li = document.createElement("li");
      li.textContent = warning;
      $("warnings").append(li);
    });
    table();
    $("toggle-table").addEventListener("click", () => {
      const hidden = !$("table-panel").hidden;
      $("table-panel").hidden = hidden;
      $("toggle-table").setAttribute("aria-expanded", String(!hidden));
      $("toggle-table").textContent = hidden ? "View data table" : "Hide data table";
    });
    $("table-previous").addEventListener("click", () => { page = Math.max(0, page - 1); table(); });
    $("table-next").addEventListener("click", () => { page++; table(); });
    $("theme-toggle").addEventListener("click", () => {
      document.documentElement.dataset.theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
      if (chart && !failed) chart.setOption(option(), {notMerge: true});
    });
    $("reset-chart").addEventListener("click", () => {
      if (chart && !failed) { chart.clear(); chart.setOption(option(), {notMerge: true}); }
    });
    $("download-png").addEventListener("click", async () => {
      if (!chart || failed) return;
      const backgroundColor = document.documentElement.dataset.theme === "light" ? "#ffffff" : "#141d2e";
      try {
        if (payload.renderer !== "svg" || payload.three_d) {
          // GL layers are composited only at their native backing-store ratio; resampling drops the plot.
          const pixelRatio = payload.three_d ?
            (typeof chart.getDevicePixelRatio === "function" ? chart.getDevicePixelRatio() : 1) : 2;
          downloadPng(chart.getDataURL({type: "png", pixelRatio, backgroundColor}));
        } else {
          const svg = chart.renderToSVGString();
          const url = URL.createObjectURL(new Blob([svg], {type: "image/svg+xml"}));
          try {
            const image = new Image();
            image.src = url;
            await image.decode();
            const canvas = document.createElement("canvas");
            canvas.width = chart.getWidth() * 2;
            canvas.height = chart.getHeight() * 2;
            const context = canvas.getContext("2d");
            context.fillStyle = backgroundColor;
            context.fillRect(0, 0, canvas.width, canvas.height);
            context.drawImage(image, 0, 0, canvas.width, canvas.height);
            downloadPng(canvas.toDataURL("image/png"));
          } finally { URL.revokeObjectURL(url); }
        }
      } catch (_) {
        status("error", "PNG export failed in this browser. The chart and data table remain available.");
        showTable();
      }
    });
    $("download-csv").hidden = !payload.csv;
    $("download-csv").addEventListener("click", () => {
      // Neutralize spreadsheet formula injection, including leading control/space characters.
      const cell = (value) => {
        let text = String(value);
        if (/^[\s]*[=+\-@]/.test(text) || /^[\t\r\n]/.test(text)) text = "'" + text;
        return '"' + text.replace(/"/g, '""') + '"';
      };
      const rows = [payload.columns.map((column) => column.label), ...payload.display_rows];
      const csv = "\ufeff" + rows.map((row) => row.map(cell).join(",")).join("\r\n");
      const url = URL.createObjectURL(new Blob([csv], {type: "text/csv;charset=utf-8"}));
      download(url, "sqlmem-chart-data.csv");
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
    mount();
  } catch (_) {
    fail("error", "Chart data could not be loaded. Regenerate this private artifact.");
  }
})();
