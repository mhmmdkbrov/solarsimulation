// Dataset selection shared by the three pages. Datasets are static JSON files built by `python -m solarsim.build`
// (PVGIS does not allow browser calls: PVGIS 5.x forbids AJAX, PVGIS 6 has a strict CORS policy). A dataset for any
// coordinate can be made with `python -m solarsim.cli dataset ...` and opened here from a local file.
const DataStore = (() => {
  const LAST_OK_KEY = "solarsim-last-ok-dataset";
  const REQUIRED = ["version", "dataset", "site", "inputs", "areas", "annual", "hourly"];

  function validate(D) {
    const miss = REQUIRED.filter(k => !(k in D));
    if (miss.length) throw new Error(`fayl tam deyil: ${miss.join(", ")} yoxdur`);
    if (!D.hourly.n || D.hourly.ghi.length !== D.hourly.n) throw new Error("saatlıq məlumatın uzunluğu uyğun gəlmir");
    if (!D.version.model || !String(D.version.model).startsWith("2.")) throw new Error(`model versiyası ${D.version.model} dəstəklənmir (2.x lazımdır)`);
    return D;
  }

  async function fetchJSON(url) {
    const r = await fetch(url, { cache: "no-cache" });
    if (!r.ok) throw new Error(`${url}: HTTP ${r.status}`);
    return r.json();
  }

  // Renders the selector into `host`, calls onLoading() immediately when the choice changes (pages must clear old
  // results there) and onLoad(D) / onError(msg, retry) afterwards.
  async function mount(host, { onLoading, onLoad, onError, initial }) {
    host.innerHTML = `<div class="ds-row">
        <label class="ds-lbl" for="ds-select">Məkan və məlumat dəsti</label>
        <select id="ds-select" class="ds-select"><option>yüklənir…</option></select>
        <label class="ds-file">Öz məlumat dəstini aç (JSON)<input type="file" id="ds-file" accept=".json,application/json"></label>
      </div>
      <p class="ds-msg" id="ds-msg" role="status"></p>`;
    const sel = host.querySelector("#ds-select"), msg = host.querySelector("#ds-msg"), file = host.querySelector("#ds-file");
    let index = [];
    try { index = (await fetchJSON("data/index.json")).datasets; }
    catch (e) { msg.textContent = `Məlumat siyahısı yüklənmədi: ${e.message}`; }
    const label = d => `${d.name} — ${d.api_version.startsWith("6") ? "PVGIS 6 TMY (beta)" : "PVGIS 5.3 TMY"}`;
    sel.innerHTML = index.map(d => `<option value="${d.id}">${label(d)}</option>`).join("") + `<option value="__file" disabled>yerli fayl</option>`;
    let lastOk = null;
    try { lastOk = localStorage.getItem(LAST_OK_KEY); } catch (e) {}
    const want = initial || (location.hash.length > 1 ? location.hash.slice(1) : null) || lastOk || (index[0] && index[0].id);
    if (want && index.some(d => d.id === want)) sel.value = want;

    async function load(id) {
      const d = index.find(x => x.id === id);
      if (!d) return;
      onLoading(label(d));
      msg.textContent = `${label(d)} yüklənir…`;
      try {
        const D = validate(await fetchJSON(d.file));
        msg.textContent = "";
        try { localStorage.setItem(LAST_OK_KEY, id); } catch (e) {}
        if (location.hash.slice(1) !== id) history.replaceState(null, "", `#${id}`);
        onLoad(D);
      } catch (e) {
        const fallback = lastOk && lastOk !== id && index.some(x => x.id === lastOk) ? lastOk : null;
        msg.innerHTML = `<b>Məlumat gəlmədi:</b> ${e.message}.` + (fallback
          ? ` <button type="button" class="ds-fallback">Son yoxlanmış dəsti aç: ${label(index.find(x => x.id === fallback))}</button>` : "");
        const b = msg.querySelector(".ds-fallback");
        if (b) b.addEventListener("click", () => { sel.value = fallback; load(fallback); });
        onError(e.message);
      }
    }
    sel.addEventListener("change", () => load(sel.value));
    file.addEventListener("change", async () => {
      const f = file.files && file.files[0];
      if (!f) return;
      onLoading(f.name);
      try {
        const D = validate(JSON.parse(await f.text()));
        D.dataset.label = `${D.dataset.label || f.name} (yerli fayl: ${f.name})`;
        sel.value = "__file";
        msg.textContent = `Yerli fayl açıldı: ${f.name}`;
        onLoad(D);
      } catch (e) {
        msg.innerHTML = `<b>Fayl oxunmadı:</b> ${e.message}. Faylı <code>python -m solarsim.cli dataset</code> ilə yaradın.`;
        onError(e.message);
      }
    });
    if (sel.value && sel.value !== "__file") await load(sel.value);
    return { reload: () => load(sel.value) };
  }

  // short provenance line for page headers
  function provenance(D) {
    const m = D.dataset, s = D.site;
    const yrs = m.years ? `${m.years[0]}–${m.years[1]}` : "";
    return `${s.name} (${fmt(s.latitude, 4)}° N, ${fmt(s.longitude, 4)}° E, ${fmt(s.elevation_m ?? 0, 0)} m) · ` +
           `${m.api ? `PVGIS ${m.api_version.split(" ")[0]}` : m.source_label} ${m.kind === "TMY" ? "TMY" : m.kind} ${yrs} · ` +
           `${m.radiation_db || ""} · addım ${fmt(D.hourly.step_h, 2)} saat · model v${D.version.model}`;
  }
  function fmt(v, d) {
    if (!isFinite(v)) return "—";
    const s = Math.abs(v).toFixed(d), [i, f] = s.split(".");
    return (v < 0 && Number(s) !== 0 ? "−" : "") + i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (f ? "," + f : "");
  }
  // up to `max` decimals, trailing zeros removed (keeps 1,526 as 1,526 and 450 as 450)
  function fmtSmart(v, max = 4) {
    const s = fmt(v, max);
    return s.includes(",") ? s.replace(/,?0+$/, "") : s;
  }
  // parameter values of any type (numbers, ranges, booleans, text) in Azerbaijani notation
  function fmtValue(v) {
    if (v === null || v === undefined) return "məkan seçimi";
    if (typeof v === "boolean") return v ? "bəli" : "xeyr";
    if (typeof v === "number") return fmtSmart(v);
    if (Array.isArray(v)) return v.map(fmtValue).join(" … ");
    return String(v);
  }
  // dataset labels come from Python with decimal points in coordinates: convert those (not version numbers)
  const label = D => String(D.dataset.label || "").replace(/(\d+)\.(\d+)°/g, "$1,$2°").replace(/(^|[\s(,])-(\d)/g, "$1−$2");
  return { mount, validate, provenance, fmt, fmtSmart, fmtValue, label };
})();
if (typeof module !== "undefined") module.exports = DataStore;
