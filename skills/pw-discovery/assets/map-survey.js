/* The map's Survey view. discovery-map-template.html loads this file from beside itself, and `kb_tool map` puts it
   inside each map. It shows what a core job's survey asks and, when there is an estimate from the interviews, where
   the needs look unmet. Every figure and every zone comes from the map's data (generated.survey: kb_survey's status
   and results); this file computes none. It uses the map's M, t, esc, setDrawer and the helpers beside them, and
   defines one global, renderSvView. Every word is a map.sv.* label; the study's own text is always escaped. */
var renderSvView = (() => {
  const view = document.getElementById("svview");
  const ui = {job: null, theme: null};
  const L = (key, vars) => esc(t(key, vars));
  const ZONES = {unmet: "map.sv.zone.unmet", served: "map.sv.zone.served", over: "map.sv.zone.over"};
  const zoneName = zone => hasKey(ZONES, zone) ? t(ZONES[zone]) : "";
  // kb_map puts in the map only the entries kb_survey reads, at most one per job and layer
  const stored = (layer, job) => ((M.raw[layer] || {}).jobs || []).find(e => e.job === job) || null;
  const stateOf = job => (M.made && M.made.survey || {})[job] || null;
  const themeName = id => (M.themes.find(tm => tm.id === id) || {}).label || "";
  const drawn = res => res.needs.filter(n => n.n > 0 && hasKey(ZONES, n.zone));
  const tenth = v => Number(v).toLocaleString(locale(), {minimumFractionDigits: 1, maximumFractionDigits: 1});

  // the source strip: no ratings yet, or an estimate and how much of it rests on evidence; then what is out of date
  function strip(st, res) {
    const why = [st.new_needs.length ? t("map.sv.new_needs", {n: st.new_needs.length}) : "",
      st.gone_needs.length ? t("map.sv.gone_needs", {n: st.gone_needs.length}) : "",
      st.estimate_old && res ? t("map.sv.estimate_old") : ""];
    const cover = res && res.coverage, parts = cover && (cover.said && cover.context ? "map.sv.coverage_both"
      : cover.said ? "map.sv.coverage_said" : cover.context ? "map.sv.coverage_context" : "");
    const head = res  // a part with no rating is not named: never "0 from context"
      ? `<b>${L("map.sv.estimate_note", {n: res.people})}</b><p>${esc(sentences(t("map.sv.coverage",
        {n: cover.cells, possible: res.possible}), parts ? t(parts, {said: cover.said, context: cover.context}) : ""))}</p>`
      : `<b>${L("map.sv.no_ratings")}</b><p>${esc(sentences(t("map.sv.ready", {n: st.needs, version: st.version}),
        t("map.sv.minutes", {n: st.minutes}), t("map.sv.how_estimate")))}</p>`;
    const flag = sentences(...why);
    return `<div class="sv-strip${res ? " sv-dash" : ""}">${head}${flag ? `<div class="flag">${esc(flag)}</div>` : ""}</div>`;
  }

  // how much it matters across, how well it is served today up, both 0 to 10; the zones follow the method's rule
  function chart(res) {
    const W = 560, H = 440, left = 58, right = 14, top = 14, bottom = 50;
    const x = v => left + v / 10 * (W - left - right), y = v => H - bottom - v / 10 * (H - top - bottom);
    let s = `<svg viewBox="0 0 ${W} ${H}" role="group" aria-label="${L("map.sv.chart_aria")}">`
      + `<polygon class="sv-zu" points="${x(5)},${y(0)} ${x(10)},${y(0)} ${x(10)},${y(10)}"/>`
      + `<polygon class="sv-zo" points="${x(0)},${y(0)} ${x(10)},${y(10)} ${x(0)},${y(10)}"/>`;
    for(let v = 0; v <= 10; v += 2) {
      s += `<line class="sv-gl" x1="${x(v)}" y1="${y(0)}" x2="${x(v)}" y2="${y(10)}"/>`
        + `<line class="sv-gl" x1="${x(0)}" y1="${y(v)}" x2="${x(10)}" y2="${y(v)}"/>`
        + `<text x="${x(v)}" y="${y(0) + 18}" text-anchor="middle">${v}</text>`
        + `<text x="${x(0) - 8}" y="${y(v) + 4}" text-anchor="end">${v}</text>`;
    }
    s += `<text class="sv-wm" x="${x(5)}" y="${y(9)}" text-anchor="middle" aria-hidden="true">${L("map.sv.estimate")}</text>`
      + `<text class="sv-zl" x="${x(8.6)}" y="${y(1.3)}" text-anchor="middle">${L("map.sv.zone.unmet")}</text>`
      + `<text class="sv-zl" x="${x(2.4)}" y="${y(7.4)}" text-anchor="middle">${L("map.sv.zone.over")}</text>`
      + `<text class="sv-zl" transform="translate(${x(4.6)} ${y(2.6)}) rotate(-38)" text-anchor="middle">${L("map.sv.zone.served")}</text>`
      + `<text x="${x(5)}" y="${H - 6}" text-anchor="middle">${L("map.sv.axis_x")} →</text>`
      + `<text transform="translate(14 ${y(5)}) rotate(-90)" text-anchor="middle">${L("map.sv.axis_y")} →</text>`;
    const dim = n => !!ui.theme && n.theme !== ui.theme;
    drawn(res).sort((a, b) => dim(b) - dim(a)).forEach(n => {
      const cx = x(n.importance), cy = y(n.satisfaction), cls = (n.ranked ? "" : " sv-one") + (dim(n) ? " sv-dim" : "");
      const say = L("map.sv.dot_aria", {need: n.text, zone: zoneName(n.zone)});
      s += `<g class="sv-dot sv-est${cls}" data-ref="${esc(n.outcome)}" tabindex="0" role="button" aria-label="${say}">`
        + `<circle class="sv-hit" cx="${cx}" cy="${cy}" r="13"/><circle class="sv-mark" cx="${cx}" cy="${cy}" r="${n.ranked ? 6 : 3.5}"/></g>`;
    });
    return s + "</svg>";
  }

  // the same data for people who cannot use the chart, ordered as the list is: most people first, then the figure
  function table(res) {
    const head = ["map.sv.col.need", "map.sv.col.zone", "map.sv.col.matters", "map.sv.col.served", "map.sv.col.people"];
    const rows = drawn(res).sort((a, b) => b.n - a.n || b.figure - a.figure).map(n => `<tr data-ref="${esc(n.outcome)}">`
      + `<th scope="row"><button type="button" class="solname">${esc(n.text)}</button></th>`
      + `<td data-l="${L(head[1])}">${esc(zoneName(n.zone))}${n.ranked ? "" : `<small>${L("map.sv.too_few")}</small>`}</td>`
      + `<td data-l="${L(head[2])}">${tenth(n.importance)}</td><td data-l="${L(head[3])}">${tenth(n.satisfaction)}</td>`
      + `<td data-l="${L(head[4])}">${L("map.sv.of_people", {rated: n.n, n: res.people})}</td></tr>`);
    return `<details class="sv-more"><summary>${L("map.sv.table")}</summary><div class="twrap"><table class="soltable sv-table">`
      + `<caption>${L("map.sv.chart_source", {n: res.people})}</caption><thead><tr>${head.map(k => `<th scope="col">${L(k)}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table></div></details>`;
  }

  // what looks unmet: in the order of results().unmet, no rank numbers, "Estimate" first on every line
  function unmet(res) {
    const byRef = Object.fromEntries(res.needs.map(n => [n.outcome, n]));
    const line = n => `<li data-ref="${esc(n.outcome)}"><button type="button" class="oitem sv-line"><span>`
      + `<span class="tag sv-tag">${L("map.sv.estimate")}</span> <span class="sv-need">${esc(n.text)}</span><small>`
      + (themeName(n.theme) ? `<span class="tag">${esc(themeName(n.theme))}</span> ` : "")
      + `${L("map.sv.unmet_line", {n: n.satisfied, matters: n.matters, rated: n.n})} `
      + (n.n < 3 ? `<span class="sv-thin">${esc(sentences(t("map.sv.rated_for", {rated: n.n, n: res.people}), t("map.sv.few")))}</span>`
        : L("map.sv.rated_for", {rated: n.n, n: res.people})) + "</small></span></button></li>";
    const list = res.unmet.map(ref => byRef[ref]).filter(Boolean);
    return `<h3>${L("map.sv.unmet_h")}</h3><p class="ov-note">${L("map.sv.unmet_intro")}</p>`
      + (list.length ? `<ol class="olist sv-unmet">${list.map(line).join("")}</ol>` : `<p class="ov-todo">${L("map.sv.none_unmet")}</p>`)
      + (res.single ? `<p class="hint sv-single">${L("map.sv.single", {n: res.single})}</p>` : "");
  }

  function estimate(res) {
    const chips = M.themes.length ? `<div class="tags sv-chips" role="group" aria-label="${L("map.sv.themes_aria")}">`
      + M.themes.map(tm => `<button type="button" class="tag" data-theme="${esc(tm.id)}" aria-pressed="${ui.theme === tm.id}">${esc(tm.label)}</button>`).join("")
      + "</div>" : "";
    return `<h3>${L("map.sv.chart_h")}</h3><p class="ov-note">${L("map.sv.chart_intro")}</p>${chips}`
      + `<div class="tcard sv-chart"><p class="sv-src">${L("map.sv.chart_source", {n: res.people})}</p>${chart(res)}`
      + `<p class="sv-scale">${L("map.sv.scale")}</p><div class="sv-legend"><span><i class="sv-key"></i>${L("map.sv.legend_est")}</span>`
      + `<span><i class="sv-key sv-small"></i>${L("map.sv.legend_one")}</span></div></div>${table(res)}${unmet(res)}`
      + `<h3>${L("map.sv.groups_h")}</h3><p class="ov-todo">${L("map.sv.groups_need_answers")}</p>`;
  }

  // what the survey asks, in its order: the frame, who answers, the needs step by step, then about the person
  function questions(entry, st, res) {
    const steps = Object.fromEntries(M.steps.map(s => [s.key, s.text]));
    const choices = list => `<div class="tags">${list.filter(Boolean).map(c => `<span class="tag">${esc(c)}</span>`).join("")}</div>`;
    const explain = text => text ? `<small>${esc(text)}</small>` : "";
    const gate = entry.gate || {};
    let needs = "", last = null;
    (entry.needs || []).forEach(n => {
      const step = String(n.outcome).split(".").slice(0, 2).join(".");
      if(step !== last) needs += `${last ? "</ol>" : ""}<h4><span class="mk-numh">${esc(step)}</span> ${esc(steps[step] || "")}</h4><ol>`;
      last = step;
      needs += `<li><span class="sv-need">${esc(n.text)}</span>${explain(n.explain)}</li>`;
    });
    const profile = (entry.profile || []).map(q => `<p class="sv-ask">${esc(q.text)}</p>${explain(q.explain)}`
      + choices([...(q.choices || []).map(c => c && c.label), q.other])).join("");
    return `<details class="sv-more sv-qs"${res ? "" : " open"}><summary>${L("map.sv.questions_h")}</summary>`
      + `<p class="ov-note">${esc(sentences(t("map.sv.questions_intro", {version: st.version}), res ? t("map.sv.questions_estimated") : ""))}</p>`
      + (entry.frame ? `<h4>${L("map.sv.frame_h")}</h4><p>${esc(entry.frame)}</p>` : "")
      + `<h4>${L("map.sv.gate_h")}</h4><p class="sv-ask">${esc(gate.text)}</p>${explain(gate.explain)}${choices([gate.yes, gate.no])}`
      + `<h4>${L("map.sv.needs_h")}</h4>${needs}${last ? "</ol>" : ""}`
      + (profile ? `<h4>${L("map.sv.profile_h")}</h4>${profile}` : "") + "</details>";
  }

  // the drawer: the need, its figures in words, and each person's two ratings with the words they rest on
  function openNeed(ref) {
    const found = stateOf(M.job), res = found && found.results, n = res && res.needs.find(x => x.outcome === ref);
    if(!n) return;
    const cells = ((stored("simulation", M.job) || {}).cells || [])
      .filter(c => c && String(c.outcome) === ref && M.ivById[String(c.interview)]);
    const tags = [n.outcome, zoneName(n.zone), themeName(n.theme)].filter(Boolean).map(x => `<span class="tag">${esc(x)}</span>`);
    const body = `<p class="hint">${L("map.sv.estimate_note", {n: res.people})}</p><div class="tags">${tags.join("")}</div>`
      + `<p>${esc(sentences(t("map.sv.unmet_line", {n: n.satisfied, matters: n.matters, rated: n.n}),
        t("map.sv.rated_for", {rated: n.n, n: res.people})))}</p><div class="sect">${L("map.sv.drawer_people", {n: cells.length})}</div>`
      + `<p class="sv-how">${L("map.sv.drawer_how")}</p>`
      + cells.map(c => `<div class="sv-cell"><div class="qwho"><button type="button" class="sv-who" data-person="${esc(c.interview)}">`
        + `${esc(M.ivById[String(c.interview)].name)}</button></div><div class="sv-rates"><span class="tag sv-tag">${L("map.sv.estimate")}</span> ${L("map.sv.matters", {n: c.importance})} · `
        + `${L("map.sv.served", {n: c.satisfaction})}</div><p class="hint">${L(c.basis === "said" ? "map.sv.basis_said" : "map.sv.basis_context")} `
        + `${esc(c.why || "")}</p><blockquote>${esc(c.quote || "")}</blockquote></div>`).join("");
    setDrawer(t("map.sv.estimate"), n.text, body);
    view.querySelectorAll(".sv-dot").forEach(d => d.classList.toggle("sv-sel", d.dataset.ref === ref));
  }

  function render() {
    const found = stateOf(M.job), entry = stored("survey", M.job);
    if(!found || !entry) { view.innerHTML = ""; return; }
    if(ui.job !== M.job) { ui.job = M.job; ui.theme = null; }
    const st = found.status, res = found.results;
    view.innerHTML = `<div class="solin">`
      + `<h2>${many() ? L("map.sv.title_job", {job: jobName(M.job)}) : L("map.sv.title")}</h2>${strip(st, res)}`
      + (res ? estimate(res) : "") + questions(entry, st, res)
      + `<details class="sv-more"><summary>${L("map.sv.method_h")}</summary><p>${L("map.sv.method_scale")}</p>`
      + `<p>${L("map.sv.method_figure")}</p><p>${L("map.sv.method_ranked")}</p></details></div>`;
  }

  view.addEventListener("click", e => {
    const chip = e.target.closest(".sv-chips > button");
    if(chip) {
      ui.theme = ui.theme === chip.dataset.theme ? null : chip.dataset.theme;
      render();
      const again = [...view.querySelectorAll(".sv-chips > button")].find(b => b.dataset.theme === chip.dataset.theme);
      if(again) again.focus();
      return;
    }
    const hit = e.target.closest(".sv-dot, [data-ref] button");
    if(hit) openNeed(hit.closest("[data-ref]").dataset.ref);
  });
  view.addEventListener("keydown", e => {
    const dot = e.target.closest(".sv-dot");
    if(dot && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); openNeed(dot.dataset.ref); }
  });
  return render;
})();
