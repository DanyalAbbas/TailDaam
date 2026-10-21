/* HACK INSIGHT frontend — served as static files by FastAPI's app.frontend().
   No framework, no build step. Every figure comes from /api/overview, /api/model
   or /ask; nothing is typed into the markup. */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const state = {
  overview: null,
  model: null,
  health: null,
  groups: [],
  groupType: "year",
  lang: "en",
  priceKey: "both",
};

const COLOURS = {
  petrol: "#0a6b3d",
  diesel: "#6f7a72",
  actual: "#141815",
  prediction: "#0a6b3d",
  baseline: "#9aa39b",
};

/* ---------- format ---------- */

const fmt = (v, digits = 2) =>
  v === null || v === undefined || Number.isNaN(Number(v))
    ? "—"
    : Number(v).toLocaleString("en-PK", {
        minimumFractionDigits: digits,
        maximumFractionDigits: digits,
      });

const signed = (v, digits = 2) => {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return "—";
  const n = Number(v);
  return `${n > 0 ? "+" : n < 0 ? "−" : ""}${fmt(Math.abs(n), digits)}`;
};

const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));

const inline = (s) =>
  esc(s).replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");

const day = (iso) => {
  const d = new Date(`${String(iso).slice(0, 10)}T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? String(iso)
    : new Intl.DateTimeFormat("en-GB", {
        day: "numeric", month: "short", year: "numeric", timeZone: "UTC",
      }).format(d);
};

const monthName = (ym) => {
  const d = new Date(`${ym}-01T00:00:00Z`);
  return Number.isNaN(d.getTime())
    ? ym
    : new Intl.DateTimeFormat("en-GB", {
        month: "long", year: "numeric", timeZone: "UTC",
      }).format(d);
};

const shortPublisher = (name) => {
  if (/Bureau of Statistics/i.test(name)) return "Pakistan Bureau of Statistics";
  if (/Energy Information/i.test(name)) return "US Energy Information Administration";
  if (/World Bank/i.test(name)) return "World Bank Pink Sheet";
  return name;
};

const publisherTag = (name) => {
  if (/Bureau of Statistics/i.test(name)) return "PBS";
  if (/Energy Information/i.test(name)) return "EIA";
  if (/World Bank/i.test(name)) return "WB";
  return "SRC";
};

/* ---------- data access ---------- */

async function getJSON(url) {
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

function blockError(el, message, retry) {
  el.innerHTML = `<div class="load-error">${esc(message)}
    <button type="button">Retry</button></div>`;
  $("button", el).addEventListener("click", retry);
}

/* ---------- honest SVG line chart ---------- */

function drawChart(el, { dates, series, height = 300, annotation = null, endLabels = false, cap = null, zero = false, band = null }) {
  const valid = series.flatMap((s) => s.values).filter((v) => v !== null && v !== undefined);
  if (!dates.length || !valid.length) {
    el.innerHTML = '<p class="note">No observations in this range.</p>';
    return;
  }

  const W = el.clientWidth && el.clientWidth < 560 ? 420 : 840;
  const H = height;
  const pad = { l: W < 560 ? 38 : 46, r: 14, t: 18, b: 30 };
  const iw = W - pad.l - pad.r;
  const ih = H - pad.t - pad.b;

  let lo = Math.min(...valid), hi = Math.max(...valid);
  let step;
  if (cap) {
    hi = cap;
    step = cap / 4;
    lo = 0;
  } else {
    const rawStep = Math.max(hi - lo, 1) / 4;
    const magnitude = 10 ** Math.floor(Math.log10(rawStep));
    const normalised = rawStep / magnitude;
    step = (normalised <= 1 ? 1 : normalised <= 2 ? 2 : normalised <= 5 ? 5 : 10) * magnitude;
    lo = zero ? 0 : Math.max(0, Math.floor(lo / step) * step);
    hi = Math.ceil(hi / step) * step;
  }
  const ticks = Math.max(2, Math.round((hi - lo) / step));

  const times = dates.map((d) => Date.parse(`${String(d).slice(0, 10)}T00:00:00Z`));
  const t0 = times[0], t1 = times[times.length - 1] || t0 + 1;
  const x = (i) => pad.l + ((times[i] - t0) / Math.max(t1 - t0, 1)) * iw;
  const y = (v) => pad.t + ih - ((v - lo) / Math.max(hi - lo, 1)) * ih;

  const clipId = `plot-${Math.random().toString(36).slice(2, 9)}`;
  let svg = `<svg viewBox="0 0 ${W} ${H}" role="img" tabindex="0"
    aria-label="Interactive chart: ${esc(series.map((s) => s.name).join(", "))}. Use arrow keys to inspect values.">
    <defs><clipPath id="${clipId}"><rect x="${pad.l}" y="${pad.t}" width="${iw}" height="${ih}"/></clipPath></defs>`;

  for (let i = 0; i <= ticks; i++) {
    const v = lo + step * i;
    const yy = y(v);
    svg += `<line class="gridline" x1="${pad.l}" y1="${yy.toFixed(1)}" x2="${W - pad.r}" y2="${yy.toFixed(1)}"/>`;
    svg += `<text x="${pad.l - 9}" y="${(yy + 3.5).toFixed(1)}" text-anchor="end">${fmt(v, 0)}</text>`;
  }
  svg += `<line class="baseline" x1="${pad.l}" y1="${pad.t + ih}" x2="${W - pad.r}" y2="${pad.t + ih}"/>`;

  const wanted = Math.min(W < 560 ? 4 : 6, dates.length);
  const seen = new Set();
  for (let i = 0; i < wanted; i++) {
    const target = t0 + ((t1 - t0) * i) / Math.max(wanted - 1, 1);
    let best = 0;
    for (let j = 1; j < times.length; j++) {
      if (Math.abs(times[j] - target) < Math.abs(times[best] - target)) best = j;
    }
    if (seen.has(best)) continue;
    seen.add(best);
    const label = new Intl.DateTimeFormat("en-GB", {
      month: "short", year: "2-digit", timeZone: "UTC",
    }).format(new Date(times[best]));
    svg += `<text x="${x(best).toFixed(1)}" y="${H - 10}" text-anchor="middle">${esc(label)}</text>`;
  }

  svg += `<g clip-path="url(#${clipId})">`;

  if (band) {
    const top = [], bottom = [];
    band.upper.forEach((v, i) => {
      if (v == null || dates[i] == null) return;
      top.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    });
    band.lower.forEach((v, i) => {
      if (v == null || dates[i] == null) return;
      bottom.push(`${x(i).toFixed(1)},${y(v).toFixed(1)}`);
    });
    if (top.length) {
      svg += `<polygon points="${top.join(" ")} ${bottom.reverse().join(" ")}" fill="${band.colour || COLOURS.prediction}" fill-opacity="0.13" stroke="none"/>`;
    }
  }

  series.forEach((s, si) => {
    const colour = s.colour || COLOURS.petrol;
    let path = "";
    let open = false;
    s.values.forEach((v, i) => {
      if (v === null || v === undefined) { open = false; return; }
      path += `${open ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)} `;
      open = true;
    });
    svg += `<path class="line" d="${path}" stroke="${colour}"/>`;

    s.values.forEach((v, i) => {
      if (v === null || v === undefined) return;
      svg += `<circle cx="${x(i).toFixed(1)}" cy="${y(v).toFixed(1)}" r="8" fill="transparent">
        <title>${esc(s.name)} · ${esc(day(dates[i]))}: ${fmt(v)}${s.unit || ""}</title></circle>`;
    });

    if (endLabels) {
      const lastIdx = s.values.map((v, i) => (v === null || v === undefined ? -1 : i)).filter((i) => i >= 0).pop();
      if (lastIdx !== undefined) {
        const lx = x(lastIdx), ly = y(s.values[lastIdx]);
        svg += `<circle class="last-dot" cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="3.4" fill="${colour}"/>`;
        svg += `<text x="${(lx - 5).toFixed(1)}" y="${(ly - 9).toFixed(1)}" text-anchor="end" fill="${colour}" style="font-weight:500">${fmt(s.values[lastIdx])}</text>`;
      }
    }
  });

  svg += `</g>`;

  if (cap) {
    series.forEach((s) => {
      s.values.forEach((v, i) => {
        if (v == null || v <= cap) return;
        const cx = x(i);
        svg += `<path d="M${(cx - 4).toFixed(1)},${pad.t + 6} L${(cx + 4).toFixed(1)},${pad.t + 6} L${cx.toFixed(1)},${pad.t} Z" fill="${s.colour || COLOURS.petrol}">
          <title>${esc(s.name)} · ${esc(day(dates[i]))}: ${fmt(v)} — off scale</title></path>`;
      });
    });
  }

  if (annotation) {
    const idx = dates.findIndex((d) => String(d).slice(0, 10) === annotation.date);
    if (idx >= 0 && series[annotation.series]?.values[idx] != null) {
      const v = series[annotation.series].values[idx];
      const cx = x(idx), cy = y(v);
      svg += `<line x1="${cx.toFixed(1)}" y1="${pad.t}" x2="${cx.toFixed(1)}" y2="${(pad.t + ih).toFixed(1)}" stroke="#d8d7cc" stroke-width="1" stroke-dasharray="2 4"/>`;
      svg += `<circle cx="${cx.toFixed(1)}" cy="${cy.toFixed(1)}" r="4.5" fill="var(--surface)" stroke="${COLOURS.diesel}" stroke-width="2"/>`;
      const flip = cx > W - 190;
      svg += `<text x="${(cx + (flip ? -8 : 8)).toFixed(1)}" y="${(cy - 9).toFixed(1)}" text-anchor="${flip ? "end" : "start"}" fill="#626c64">${esc(annotation.label)}</text>`;
    }
  }

  const xPositions = dates.map((_, i) => x(i));
  const yPositions = series.map((s) => s.values.map((v) => (v == null ? null : y(v))));
  svg += `<g class="hover-layer" aria-hidden="true">
    <line class="crosshair" x1="${pad.l}" y1="${pad.t}" x2="${pad.l}" y2="${pad.t + ih}"/>
    ${series.map((s) => `<circle class="hover-dot" r="4" fill="${s.colour || COLOURS.petrol}" cx="${pad.l}" cy="${pad.t}"/>`).join("")}
  </g>`;
  svg += "</svg>";

  const legendItems = series.map((s) =>
    `<span><i style="background:${s.colour || COLOURS.petrol}"></i>${esc(s.name)}</span>`);
  if (band) {
    legendItems.push(`<span><i style="background:${band.colour || COLOURS.prediction};opacity:.25;height:9px"></i>${esc(band.name || "90% interval")}</span>`);
  }
  const legend = legendItems.length > 1
    ? `<div class="chart-legend">${legendItems.join("")}</div>`
    : "";

  el.innerHTML = svg + legend;
  const monthly = dates.length > 0 && dates.every((d) => /^\d{4}-\d{2}-01$/.test(d));
  const labelDate = monthly
    ? (d) => new Intl.DateTimeFormat("en-GB", { month: "short", year: "numeric", timeZone: "UTC" })
      .format(new Date(`${String(d).slice(0, 10)}T00:00:00Z`))
    : day;
  wireChart(el, { dates, series, xPositions, yPositions, pad, W, H, labelDate });
}

/* Hover, touch and keyboard inspection: the chart is a reading surface, not a
   picture. The native <title> stays as a fallback. */
function wireChart(el, { dates, series, xPositions, yPositions, pad, W, H, labelDate }) {
  const svg = el.querySelector("svg");
  if (!svg) return;
  const tip = document.createElement("div");
  tip.className = "chart-tooltip";
  tip.hidden = true;
  tip.setAttribute("role", "status");
  el.appendChild(tip);

  const cross = svg.querySelector(".crosshair");
  const dots = [...svg.querySelectorAll(".hover-dot")];
  const plotLeft = pad.l;
  const plotRight = W - pad.r;
  let current = null;

  const hide = () => {
    current = null;
    tip.hidden = true;
    el.classList.remove("is-hovering");
  };

  const show = (i) => {
    if (i == null || i < 0 || i >= dates.length) return;
    current = i;
    const x = xPositions[i];
    cross.setAttribute("x1", x);
    cross.setAttribute("x2", x);
    series.forEach((s, si) => {
      const dot = dots[si];
      const yy = yPositions[si][i];
      if (yy == null) { dot.style.display = "none"; return; }
      dot.style.display = "";
      dot.setAttribute("cx", x);
      dot.setAttribute("cy", yy);
    });

    const rows = series.map((s, si) => {
      const v = s.values[i];
      return `<div class="tt-row"><i style="background:${s.colour || COLOURS.petrol}"></i>
        <span>${esc(s.name)}</span>
        <b>${v == null ? "—" : fmt(v)}</b>
        <small>${v == null ? "" : esc(s.unit || "")}</small></div>`;
    }).join("");
    tip.innerHTML = `<p class="tt-date">${esc(labelDate(dates[i]))}</p>${rows}`;
    tip.hidden = false;
    el.classList.add("is-hovering");

    const rect = svg.getBoundingClientRect();
    const px = (x / W) * rect.width;
    const top = Math.min(...series.map((s, si) => yPositions[si][i]).filter((v) => v != null));
    const yPx = (top / H) * rect.height;
    const half = Math.min(tip.offsetWidth / 2, rect.width / 2 - 6);
    tip.classList.toggle("below", yPx < 130);
    tip.style.left = `${Math.max(half, Math.min(rect.width - half, px))}px`;
    tip.style.top = `${Math.max(8, yPx)}px`;
  };

  const nearest = (clientX) => {
    const rect = svg.getBoundingClientRect();
    const vx = ((clientX - rect.left) / Math.max(rect.width, 1)) * W;
    let best = 0;
    let bestDistance = Infinity;
    xPositions.forEach((x, i) => {
      if (x < plotLeft - 8 || x > plotRight + 8) return;
      const d = Math.abs(x - vx);
      if (d < bestDistance) { bestDistance = d; best = i; }
    });
    return best;
  };

  svg.setAttribute("tabindex", "0");
  svg.addEventListener("pointermove", (e) => show(nearest(e.clientX)));
  svg.addEventListener("pointerleave", hide);
  svg.addEventListener("focus", () => show(current ?? dates.length - 1));
  svg.addEventListener("blur", hide);
  svg.addEventListener("keydown", (e) => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      const base = current ?? dates.length - 1;
      show(Math.max(0, Math.min(dates.length - 1, base + (e.key === "ArrowRight" ? 1 : -1))));
    } else if (e.key === "Home") {
      e.preventDefault(); show(0);
    } else if (e.key === "End") {
      e.preventDefault(); show(dates.length - 1);
    } else if (e.key === "Escape") {
      hide();
    }
  });
}

/* ---------- overview ---------- */

function renderBoard(latest, weekly) {
  const board = $("#price-board");
  if (!latest?.length) {
    board.innerHTML = '<div class="load-error">No gold prices found. Run `make data`.</div>';
    return;
  }
  const order = (e) => (/petrol/i.test(e) ? 0 : 1);
  const rows = [...latest].sort((a, b) => order(a.entity) - order(b.entity));
  const period = rows.map((r) => r.latest_date).sort().at(-1);
  const key = (entity) => (/diesel/i.test(entity) ? "hsd" : "petrol");

  $("#board-period").textContent = `Week ended ${day(period)}`;
  $("#board-count").textContent = `${weekly?.dates?.length ?? "—"} weekly reports`;
  $("#board-prices").innerHTML = rows.map((r) => {
    const dir = r.change_pkr > 0 ? "up" : r.change_pkr < 0 ? "down" : "flat";
    const words = r.change_pkr > 0 ? "higher" : r.change_pkr < 0 ? "lower" : "unchanged";
    const delta = r.change_pkr === 0
      ? "Unchanged on the prior week"
      : `Rs ${fmt(Math.abs(r.change_pkr))} ${words} (${fmt(Math.abs(r.change_pct))}%) <span class="vs">vs prior week</span>`;
    return `<div class="board-price">
      <span class="fuel">${esc(r.entity.replace(" price in Pakistan", ""))}</span>
      <div class="board-value"><span>${fmt(r.latest_pkr)}</span><span class="unit">PKR / litre</span></div>
      <div class="board-delta ${dir}">${delta}</div>
      <span class="rowid">pbs:${esc(r.latest_date)}:${key(r.entity)} · ${esc(r.citation_tag)}</span>
    </div>`;
  }).join("");
}

function renderFacts(overview) {
  const q = overview.quality || {};
  const d = q.decisions || {};
  const m = overview.model || {};
  const s = overview.sources || {};
  const health = state.health || {};
  const p = overview.pipeline || {};
  const runTime = p.finished_utc || p.started_utc;
  const runLabel = runTime
    ? `${new Intl.DateTimeFormat("en-GB", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
        timeZone: "UTC", hour12: false,
      }).format(new Date(runTime))} UTC`
    : "not logged";
  const status = (q.status || "unknown").toUpperCase();
  const dot = status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "";
  const improve = m.improvement;
  const pillClass = status === "PASS" ? "pass" : status === "FAIL" ? "fail" : "warn";

  $("#facts").innerHTML = `
    <div class="fact-row">
      <dt>PBS data quality</dt>
      <dd><span class="pill ${pillClass}"><span class="status-dot ${dot}"></span>${esc(status)}</span>
        <small>${d.total ?? "—"} rules · ${d.fix ?? "—"} fix · ${d.flag ?? "—"} flags</small></dd>
    </div>
    <div class="fact-row">
      <dt>Model vs baseline</dt>
      <dd class="good">${improve == null ? "—" : `+${fmt(improve)}%`}<small>MAE ${fmt(m.challenger_mae)} vs ${fmt(m.baseline_mae)}</small></dd>
    </div>
    <div class="fact-row">
      <dt>Facts indexed</dt>
      <dd>${health.facts_indexed == null ? "—" : health.facts_indexed.toLocaleString("en-PK")}<small>${s.files ?? "—"} source files · ${s.publishers ?? "—"} publishers</small></dd>
    </div>
    <div class="fact-row">
      <dt>Last pipeline run</dt>
      <dd>${esc((p.state || "not logged").toUpperCase())}<small>${esc(runLabel)}${p.rows_gold ? ` · ${p.rows_gold.toLocaleString("en-PK")} gold rows` : ""}</small></dd>
    </div>`;
}

function renderSources(sources) {
  const list = sources?.by_publisher || [];
  $("#record-files").textContent = `${sources?.files ?? "—"} files`;
  $("#source-list").innerHTML = list.length
    ? list.map((p) => `<li>
        <div><span class="name">${esc(shortPublisher(p.publisher))}</span>
        <span class="lic">${esc(p.licences.join(" · ") || "licence recorded in manifest")}</span></div>
        <span class="count">${p.files} ${p.files === 1 ? "file" : "files"}</span>
      </li>`).join("")
    : '<li class="empty">Manifest not found.</li>';
  const h = state.health || {};
  $("#record-mode").textContent =
    `${h.facts_indexed?.toLocaleString("en-PK") ?? "—"} facts · ${h.embedding_mode ?? "—"}`;
}

function renderTitle(overview) {
  const p = overview.latest?.find((r) => /petrol/i.test(r.entity));
  const d = overview.latest?.find((r) => /diesel/i.test(r.entity));
  if (!p) return;
  const phrase = (r) => {
    if (!r) return "";
    if (r.change_pkr === 0) return "unchanged on the prior week";
    return `${r.change_pkr > 0 ? "up" : "down"} Rs ${fmt(Math.abs(r.change_pkr))} on the prior week`;
  };
  $("#overview-sub").textContent =
    `Week ended ${day(p.latest_date)}. Petrol Rs ${fmt(p.latest_pkr)}/L, ${phrase(p)}; diesel Rs ${fmt(d?.latest_pkr)}/L, ${phrase(d)}.`;
}

function renderCoverage(coverage) {
  const el = $("#coverage");
  if (!el) return;
  if (!coverage?.length) { el.innerHTML = ""; return; }
  el.innerHTML = `<p class="coverage-title">On the record</p>
    <ul class="coverage-list">${coverage.map((c) => `<li>
      <span>${esc(c.label)}<small>${esc(c.detail)}</small></span>
      <b>${Number(c.rows).toLocaleString("en-PK")}</b>
    </li>`).join("")}</ul>`;
}

function renderCity(city, latest) {
  const tbody = $("#city-table tbody");
  if (!city?.cities?.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="empty">No city annex found.</td></tr>';
    return;
  }
  $("#city-sub").textContent = `Monthly averages, ${monthName(city.month)} · ${city.cities.length} reporting locations`;

  const rows = city.cities.map((name, i) => {
    const petrol = city.petrol[i];
    const diesel = city.diesel[i];
    const delta = petrol != null && diesel != null ? diesel - petrol : null;
    return { name, petrol, diesel, delta };
  });
  state.cities = rows;

  tbody.innerHTML = rows.map((r) => `<tr data-city="${esc(r.name.toLowerCase())}">
    <td class="city">${esc(r.name)}</td>
    <td class="num">${fmt(r.petrol)}</td>
    <td class="num">${fmt(r.diesel)}</td>
    <td class="num delta-cell">${r.delta == null ? "—" : `${r.delta > 0 ? "+" : r.delta < 0 ? "−" : ""}${fmt(Math.abs(r.delta))}`}</td>
  </tr>`).join("");
}

function filterCities() {
  const q = $("#city-filter").value.trim().toLowerCase();
  $$("#city-table tbody tr").forEach((tr) => {
    tr.hidden = q.length > 0 && !tr.dataset.city.includes(q);
  });
}

/* ---------- charts on the overview ---------- */

function priceSeries(key) {
  const data = state.overview;
  if (!data) return [];
  const pick = (re, name, colour) => {
    const found = data.weekly.series.find((x) => re.test(x.name));
    return found ? { ...found, name, colour, unit: " PKR/L" } : null;
  };
  const petrol = pick(/petrol/i, "Petrol", COLOURS.petrol);
  const diesel = pick(/diesel/i, "Diesel", COLOURS.diesel);
  if (key === "petrol") return [petrol].filter(Boolean);
  if (key === "diesel") return [diesel].filter(Boolean);
  return [petrol, diesel].filter(Boolean);
}

function renderPriceChart(key) {
  const data = state.overview;
  if (!data) return;
  state.priceKey = key;
  const series = priceSeries(key);
  drawChart($("#price-chart"), {
    dates: data.weekly.dates,
    series,
    height: 300,
    endLabels: series.length === 1,
    annotation: key !== "petrol"
      ? { date: "2026-04-09", series: series.length === 2 ? 1 : 0, label: "9 Apr · 522.29, flagged" }
      : null,
  });
}

/* ---------- model ---------- */

function renderModelKpis(m) {
  const b = m.baseline || {}, c = m.challenger || {}, u = m.uncertainty || {};
  const tiles = [
    { label: "Baseline MAE", value: fmt(b.mae), sub: "Persistence, held-out months" },
    { label: "Challenger MAE", value: fmt(c.mae), sub: "HAR ridge, pre-registered α = 10" },
    {
      label: "Improvement",
      value: m.improvement_vs_baseline_pct == null ? "—" : `+${fmt(m.improvement_vs_baseline_pct)}%`,
      sub: "Relative MAE against baseline",
      good: true,
      pill: m.beats_baseline ? "beats baseline" : null,
    },
    {
      label: "90% interval coverage",
      value: `${fmt((u.empirical_coverage ?? 0) * 100, 1)}%`,
      sub: "Target 90%, empirical",
      pill: "honest intervals",
    },
  ];
  $("#model-kpis").innerHTML = tiles.map((t) => `<div class="kpi">
      <span class="kpi-label">${esc(t.label)}</span>
      <span class="kpi-value${t.good ? " good" : ""}">${esc(t.value)}</span>
      <span class="kpi-sub">${esc(t.sub)}</span>
      ${t.pill ? `<span class="kpi-pill">${esc(t.pill)}</span>` : ""}
    </div>`).join("");
}

function renderModel(m) {
  state.model = m;
  const metrics = m.metrics || {};
  renderModelKpis(metrics);

  const split = metrics.split || {};
  $("#model-stamp").textContent =
    `Held-out test · ${split.test_rows ?? "—"} months · ${day(split.test_start)} to ${day(split.test_end)}`;

  const p = m.predictions || [];
  if (p.length) {
    const CAP = 160;
    const off = p.filter((r) => r.actual > CAP);
    drawChart($("#model-chart"), {
      dates: p.map((r) => String(r.date).slice(0, 10)),
      series: [
        { name: "Actual", values: p.map((r) => r.actual), colour: COLOURS.actual, unit: "%" },
        { name: "Prediction", values: p.map((r) => r.prediction), colour: COLOURS.prediction, unit: "%" },
        { name: "Persistence", values: p.map((r) => r.baseline_prediction), colour: COLOURS.baseline, unit: "%" },
      ],
      band: {
        lower: p.map((r) => r.interval_low_90),
        upper: p.map((r) => r.interval_high_90),
        colour: COLOURS.prediction,
        name: "90% interval",
      },
      cap: CAP,
      zero: true,
      height: 300,
      endLabels: false,
    });
    $("#pred-note").textContent =
      `Annualised realised volatility of Brent, next calendar month. ${split.test_rows} held-out months, ` +
      "chronological split. The 90% interval is a residual quantile from training, not a promise. " +
      "Hover or focus the chart to inspect any month; arrow keys move the cursor." +
      (off.length
        ? ` Actual values above the chart cap of ${CAP}: ` +
          `${off.map((r) => `${String(r.date).slice(0, 7)} = ${fmt(r.actual)}`).join(", ")}. ` +
          "Off-scale marks sit at the top edge."
        : "");
  }

  state.groups = m.groups || [];
  renderGroups();

  const card = $("#model-card-text");
  const cardText = String(m.model_card || "Model card unavailable.")
    .replace(/^#\s*Model card\s*\n+/i, "");
  card.innerHTML = mdToHtml(cardText);
}

function renderGroups() {
  const rows = state.groups.filter((g) => g.group_type === state.groupType);
  $("#group-table tbody").innerHTML = rows.length
    ? rows.map((g) => `<tr>
        <td>${esc(g.group)}</td>
        <td class="num">${g.n}</td>
        <td class="num">${fmt(g.mae)}</td>
        <td class="num">${signed(g.bias)}</td>
      </tr>`).join("")
    : '<tr><td colspan="4" class="empty">No rows for this grouping.</td></tr>';
  $$("#group-switch button").forEach((b) => {
    const active = b.dataset.group === state.groupType;
    b.classList.toggle("is-active", active);
    b.setAttribute("aria-pressed", String(active));
  });
}

/* markdown-lite, for the generated model card only */
function mdToHtml(md) {
  const lines = String(md).replace(/\r/g, "").split("\n");
  const out = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (!line.trim()) { i++; continue; }

    const heading = line.match(/^(#{1,3})\s+(.*)$/);
    if (heading) {
      const level = Math.min(heading[1].length + 1, 4);
      out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      i++; continue;
    }

    if (/^\|/.test(line)) {
      const block = [];
      while (i < lines.length && /^\|/.test(lines[i])) { block.push(lines[i]); i++; }
      const cells = (row) => row.replace(/^\||\|$/g, "").split("|").map((c) => c.trim());
      const head = cells(block[0]);
      const body = block.slice(2).map(cells);
      const isNum = head.map((_, ci) => ci > 0 && body.length > 0 && body.every((r) => /^[-+−]?[\d,.]+%?$/.test(r[ci] || "")));
      out.push(`<div class="md-table"><table class="data-table"><thead><tr>${
        head.map((h, ci) => `<th scope="col" class="${isNum[ci] ? "num" : ""}">${inline(h)}</th>`).join("")
      }</tr></thead><tbody>${
        body.map((r) => `<tr>${r.map((c, ci) =>
          `<td class="${isNum[ci] ? "num" : ""}">${inline(c)}</td>`).join("")}</tr>`).join("")
      }</tbody></table></div>`);
      continue;
    }

    if (/^[-*]\s+/.test(line)) {
      const items = [];
      while (i < lines.length && /^[-*]\s+/.test(lines[i])) {
        items.push(`<li>${inline(lines[i].replace(/^[-*]\s+/, ""))}</li>`);
        i++;
      }
      out.push(`<ul>${items.join("")}</ul>`);
      continue;
    }

    const para = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,3})\s|^\||^[-*]\s+/.test(lines[i])) {
      para.push(lines[i].trim());
      i++;
    }
    out.push(`<p>${inline(para.join(" "))}</p>`);
  }
  return out.join("");
}

/* ---------- agent ---------- */

function addMessage(role, html, { refused = false, citations = [], rowIds = [], urdu = false } = {}) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}${refused ? " refused" : ""}`;
  const chips = citations.length
    ? `<div class="cites">${citations.map((c) => `<span class="cite">${esc(c)}</span>`).join("")}</div>`
    : "";
  const preview = rowIds.slice(0, 3).join(" · ");
  const rows = rowIds.length
    ? `<div class="rows-line">${rowIds.length} row id${rowIds.length === 1 ? "" : "s"} · ${esc(preview)}${rowIds.length > 3 ? ` · +${rowIds.length - 3} more` : ""}</div>`
    : "";
  wrap.innerHTML = `<p class="who">${role === "user" ? "You" : "Agent"}</p>
    <div class="bubble"${urdu ? ' dir="rtl" lang="ur"' : ""}>${html}${chips}${rows}</div>`;
  $("#messages").appendChild(wrap);
  $("#messages").scrollTop = $("#messages").scrollHeight;
}

function renderEvidence(evidence) {
  const el = $("#evidence");
  if (!evidence?.length) {
    el.className = "evidence empty";
    el.textContent = "The last answer was a refusal, so no evidence was quoted.";
    return;
  }
  el.className = "evidence";
  el.innerHTML = `<table>
      <thead><tr><th scope="col">Cite</th><th scope="col">Fact</th><th scope="col" class="num">Value</th></tr></thead>
      <tbody>${evidence.map((e) => `<tr>
        <td class="cite-cell">${esc(e.citation)}</td>
        <td>${esc(e.entity)}<span class="rid">${esc(e.row_ids)}${e.row_id_count > 8 ? ` · +${e.row_id_count - 8} more` : ""}</span></td>
        <td class="val num">${esc(e.value)} ${esc(e.unit)}</td>
      </tr>`).join("")}</tbody></table>
    <p class="score">Scores ${evidence.map((e) => e.score).join(", ")} · periods ${evidence.map((e) => String(e.period_end).slice(0, 10)).join(", ")}</p>`;
}

async function ask(question) {
  const send = $("#send");
  const lang = state.lang;
  $("#question").value = "";
  const coverage = $("#coverage");
  if (coverage) coverage.hidden = true;
  addMessage("user", `<p>${esc(question)}</p>`, { urdu: lang === "ur" });

  send.disabled = true;
  const thinking = document.createElement("div");
  thinking.className = "message assistant";
  thinking.innerHTML = '<p class="who">Agent</p><div class="bubble thinking">Retrieving the record…</div>';
  $("#messages").appendChild(thinking);
  $("#messages").scrollTop = $("#messages").scrollHeight;

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify({ question, lang }),
    });
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try { detail = (await res.json()).detail || detail; } catch { /* keep status */ }
      throw new Error(detail);
    }
    const data = await res.json();
    thinking.remove();
    const answerText = String(data.answer)
      .replace(/^\s*Evidence rows:.*$/gmi, "")
      .trim();
    const paragraphs = esc(answerText)
      .split("\n")
      .filter((line) => line.trim())
      .map((line) => `<p>${line
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/\[([A-Z][A-Z0-9-]+)\]/g, '<span class="tag">$1</span>')}</p>`)
      .join("");
    addMessage("assistant", paragraphs, {
      refused: data.refused,
      citations: data.citations || [],
      rowIds: data.row_ids || [],
      urdu: lang === "ur",
    });
    renderEvidence(data.evidence || []);
  } catch (err) {
    thinking.remove();
    addMessage("assistant", `<p>The request failed: ${esc(err.message)}. The record is still available; try again.</p>`);
  } finally {
    send.disabled = false;
    $("#question").focus();
  }
}

function renderHealth(health) {
  state.health = health;
  const facts = health.facts_indexed?.toLocaleString("en-PK") ?? "—";
  $("#agent-mode").textContent =
    health.embedding_mode === "local-tfidf"
      ? `${facts} facts · local TF-IDF`
      : `${facts} facts · ${health.embedding_mode || "—"}`;
  $("#composer-note").textContent = health.generation_mode === "groq"
    ? "Generated from retrieved rows with Groq; numbers and citations are re-verified afterwards."
    : "Extractive mode: the answer is assembled from retrieved rows, not generated prose.";
  $("#record-mode").textContent = `${facts} facts · ${health.embedding_mode || "—"}`;
}

/* ---------- loading ---------- */

function renderFreshness(overview) {
  const stamp = overview.quality?.generated_at;
  $("#freshness").textContent = stamp
    ? `Record built ${new Intl.DateTimeFormat("en-GB", {
        day: "numeric", month: "short", hour: "2-digit", minute: "2-digit",
        timeZone: "UTC", hour12: false,
      }).format(new Date(stamp))} UTC`
    : "Gold tables loaded";
}

async function loadOverview() {
  try {
    const data = await getJSON("/api/overview");
    state.overview = data;
    renderTitle(data);
    renderBoard(data.latest, data.weekly);
    renderFacts(data);
    renderSources(data.sources);
    renderCoverage(data.coverage);
    renderPriceChart(state.priceKey);
    renderCity(data.city, data.latest);
    renderFreshness(data);
    const latestDate = data.latest?.[0]?.latest_date;
    $("#footer-meta").textContent =
      `${data.sources.files} source files · ${data.sources.publishers} publishers · ` +
      `${state.health?.facts_indexed?.toLocaleString("en-PK") ?? "—"} facts · latest week ${latestDate ?? "—"}`;
  } catch (err) {
    $("#overview-sub").textContent = "The overview could not be loaded.";
    blockError($("#price-board"), "Prices could not be loaded from the API.", loadOverview);
    $("#facts").innerHTML = `<div class="fact-row"><dt>API</dt><dd>offline</dd></div>`;
  }
}

async function loadModel() {
  try {
    renderModel(await getJSON("/api/model"));
  } catch (err) {
    blockError($("#model-kpis"), "Model artifacts could not be loaded.", loadModel);
    $("#model-card-text").textContent = "Model card unavailable.";
  }
}

async function loadHealth() {
  try {
    renderHealth(await getJSON("/api/health"));
  } catch {
    $("#agent-mode").textContent = "API offline";
    $("#composer-note").textContent = "The agent API is offline. Start it with `make api`.";
  }
}

async function loadAll() {
  const btn = $("#refresh");
  btn.classList.add("is-busy");
  await loadHealth();
  await Promise.allSettled([loadOverview(), loadModel()]);
  btn.classList.remove("is-busy");
}

/* ---------- routing and wiring ---------- */

const PANELS = ["overview", "model", "agent"];

function route() {
  const name = location.hash.replace("#", "");
  const tab = PANELS.includes(name) ? name : "overview";
  PANELS.forEach((p) => { $(`#panel-${p}`).hidden = p !== tab; });
  $$(".tabs a").forEach((a) => {
    if (a.dataset.tab === tab) a.setAttribute("aria-current", "page");
    else a.removeAttribute("aria-current");
  });
  document.title = tab === "overview"
    ? "HACK INSIGHT · Pakistan fuel prices on the record"
    : `HACK INSIGHT · ${tab === "model" ? "Model" : "Insight agent"}`;
  if (location.hash !== `#${tab}`) history.replaceState(null, "", `#${tab}`);
  if (tab === "overview" && state.overview) renderPriceChart(state.priceKey);
  if (tab === "model" && state.model) renderModel(state.model);
  window.scrollTo({ top: 0, behavior: "auto" });
}

function boot() {
  window.addEventListener("hashchange", route);
  route();

  $("#refresh").addEventListener("click", loadAll);

  $$("#series-switch button").forEach((b) => b.addEventListener("click", () => {
    $$("#series-switch button").forEach((x) => {
      const active = x === b;
      x.classList.toggle("is-active", active);
      x.setAttribute("aria-pressed", String(active));
    });
    renderPriceChart(b.dataset.series);
  }));

  $$("#group-switch button").forEach((b) => b.addEventListener("click", () => {
    state.groupType = b.dataset.group;
    renderGroups();
  }));

  $$("#lang-switch button").forEach((b) => b.addEventListener("click", () => {
    state.lang = b.dataset.lang;
    $$("#lang-switch button").forEach((x) => {
      const active = x === b;
      x.classList.toggle("is-active", active);
      x.setAttribute("aria-pressed", String(active));
    });
    $("#question").placeholder = state.lang === "ur"
      ? "مثال: پاکستان میں پیٹرول کی قیمت کیا ہے؟"
      : "What was the petrol price in October 2026?";
  }));

  $$("#examples button").forEach((b) => b.addEventListener("click", () => ask(b.dataset.q)));

  $("#ask-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#question").value.trim();
    if (!q) return;
    $("#question").value = "";
    ask(q);
  });

  $("#city-filter").addEventListener("input", filterCities);

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(() => {
      if (state.overview) renderPriceChart(state.priceKey);
      if (state.model) renderModel(state.model);
    }, 160);
  });

  loadAll();
}

document.addEventListener("DOMContentLoaded", boot);
