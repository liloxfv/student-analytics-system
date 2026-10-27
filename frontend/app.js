"use strict";
const $ = (s, r = document) => r.querySelector(s);
const nf = new Intl.NumberFormat("fa-IR", { maximumFractionDigits: 1 });
const num = (v) => (v == null ? "—" : nf.format(v));
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const dshort = (d) => new Date(d + "T00:00:00").toLocaleDateString("fa-IR", { month: "short", day: "numeric" });
const dlong = (d) => new Date(d + "T00:00:00").toLocaleDateString("fa-IR", { year: "numeric", month: "long", day: "numeric" });
const todayISO = () => new Date().toISOString().slice(0, 10);

const COLORS = { great: "#5cd0a8", good: "#a5da7f", ok: "#ffc15e", low: "#ff8aa0", none: "#e1e4ee" };
const RAINBOW = ["#a99bff", "#ff9fba", "#ffc46b", "#6fd6b8", "#7cc3ff", "#ffa58c"];
const level = (s) => (s == null ? "none" : s >= 17 ? "great" : s >= 14 ? "good" : s >= 10 ? "ok" : "low");
const chip = (s) => `<span class="chip ${level(s)}">${num(s)}</span>`;

Chart.defaults.font.family = "Vazirmatn, Tahoma, sans-serif";
Chart.defaults.color = "#7a869a";
Chart.defaults.borderColor = "#f1f2f8";
let charts = [];
const killCharts = () => { charts.forEach((c) => c.destroy()); charts = []; };
const chart = (id, cfg) => { const c = new Chart($(id), cfg); charts.push(c); return c; };
const rtlPlugins = { legend: { rtl: true, textDirection: "rtl", labels: { usePointStyle: true } }, tooltip: { rtl: true, textDirection: "rtl" } };

/* ---------- helpers ---------- */
async function api(path, opts = {}) {
  let res;
  try {
    res = await fetch("/api" + path, {
      ...opts,
      headers: { "Content-Type": "application/json" },
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
  } catch {
    throw new Error("ارتباط با سرور برقرار نشد. اجرای سرور را بررسی کنید.");
  }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    let msg = data && data.detail;
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg).join("، ");
    throw new Error(msg || "خطای ناشناخته رخ داد.");
  }
  return data;
}
let toastTimer;
function toast(msg, isErr = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "show" + (isErr ? " err" : "");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (t.className = ""), 3200);
}
const guard = (fn) => async (...a) => { try { await fn(...a); } catch (e) { toast(e.message, true); } };
const dlg = $("#dlg");
const openDlg = (html) => { dlg.innerHTML = `<div class="dlg">${html}</div>`; if (!dlg.open) dlg.showModal(); };
const closeDlg = () => { killDlgChart(); dlg.close(); };
let dlgChart = null;
const killDlgChart = () => { if (dlgChart) { dlgChart.destroy(); dlgChart = null; } };
dlg.addEventListener("click", (e) => { if (e.target === dlg) closeDlg(); });
dlg.addEventListener("close", killDlgChart);
const view = $("#view");
const empty = (msg) => `<div class="panel empty">${msg}</div>`;

/* ---------- router ---------- */
const views = { dashboard, students, grades, attendance };
const titles = { dashboard: "داشبورد", students: "دانش‌آموزان", grades: "نمرات", attendance: "حضور و غیاب" };
async function go(name) {
  killCharts();
  document.querySelectorAll("#nav button").forEach((b) => b.classList.toggle("on", b.dataset.view === name));
  $("#title").textContent = titles[name];
  view.innerHTML = empty("در حال بارگذاری…");
  try { await views[name](); } catch (e) { view.innerHTML = empty(esc(e.message)); }
}
$("#nav").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) go(b.dataset.view); });
$("#today").textContent = new Date().toLocaleDateString("fa-IR", { weekday: "long", year: "numeric", month: "long", day: "numeric" });

/* ---------- dashboard ---------- */
async function dashboard() {
  const s = await api("/analytics/summary");
  if (!s.students) {
    view.innerHTML = empty("هنوز دانش‌آموزی ثبت نشده است. از بخش «دانش‌آموزان» شروع کنید.");
    return;
  }
  const att = s.attendance;
  view.innerHTML = `
  <div class="strip">
    <div><span>دانش‌آموزان</span><b>${num(s.students)}</b><em>${num(s.subjects)} درس</em></div>
    <div><span>میانگین کل نمرات</span><b>${num(s.average)}</b><em>از ۲۰ • ${num(s.grades)} نمره</em></div>
    <div><span>درصد حضور</span><b>${att.rate == null ? "—" : num(att.rate) + "٪"}</b><em>${num(att.total)} رکورد</em></div>
    <div><span>نیازمند توجه</span><b>${num(s.attention.length)}</b><em>میانگین زیر ۱۲</em></div>
  </div>
  <div class="grid g3 mt">
    <div class="panel"><h2>میانگین هر درس</h2><div class="chartbox"><canvas id="c-sub"></canvas></div></div>
    <div class="panel"><h2>میانگین کلاس‌ها</h2><ul class="rows" id="classes"></ul></div>
  </div>
  <div class="grid g2 mt">
    <div class="panel"><h2>روند میانگین نمرات در طول ترم</h2><div class="chartbox"><canvas id="c-time"></canvas></div></div>
    <div class="panel"><h2>توزیع میانگین دانش‌آموزان</h2><div class="chartbox"><canvas id="c-dist"></canvas></div></div>
  </div>
  <div class="grid g2 mt">
    <div class="panel"><h2>وضعیت حضور</h2><div class="chartbox"><canvas id="c-att"></canvas></div></div>
    <div class="panel"><h2>دانش‌آموزان نیازمند توجه</h2><ul class="rows" id="attn"></ul></div>
  </div>`;

  $("#classes").innerHTML = s.class_averages.length
    ? s.class_averages.map((c) => `<li><span>${esc(c.class_name)}</span><span class="meter"><i style="width:${(c.average / 20) * 100}%;background:${COLORS[level(c.average)]}"></i></span>${chip(c.average)}</li>`).join("")
    : `<li class="empty">داده‌ای نیست</li>`;
  $("#attn").innerHTML = s.attention.length
    ? s.attention.map((a) => `<li><span><a href="#" data-id="${a.id}" class="open">${esc(a.name)}</a> <small>${esc(a.class_name)}</small></span>${chip(a.average)}</li>`).join("")
    : `<li class="empty">همه دانش‌آموزان میانگین ۱۲ یا بالاتر دارند.</li>`;
  $("#attn").addEventListener("click", (e) => { const a = e.target.closest(".open"); if (a) { e.preventDefault(); report(a.dataset.id); } });

  const axis = { min: 0, max: 20, ticks: { callback: (v) => nf.format(v) } };
  chart("#c-sub", {
    type: "bar",
    data: { labels: s.subject_averages.map((x) => x.name), datasets: [{ data: s.subject_averages.map((x) => x.average), backgroundColor: s.subject_averages.map((_, i) => RAINBOW[i % 6]), borderRadius: 8 }] },
    options: { indexAxis: "y", maintainAspectRatio: false, plugins: { ...rtlPlugins, legend: { display: false } }, scales: { x: axis, y: { position: "right" } } },
  });
  chart("#c-time", {
    type: "line",
    data: { labels: s.timeline.map((t) => dshort(t.date)), datasets: [{ data: s.timeline.map((t) => t.average), borderColor: "#9a8bf5", backgroundColor: "#9a8bf51f", pointBackgroundColor: "#ff9fba", pointBorderColor: "#fff", pointBorderWidth: 2, fill: true, tension: 0.35, pointRadius: 6 }] },
    options: { maintainAspectRatio: false, plugins: { ...rtlPlugins, legend: { display: false } }, scales: { y: axis } },
  });
  chart("#c-dist", {
    type: "bar",
    data: { labels: s.distribution.map((d) => d.label), datasets: [{ data: s.distribution.map((d) => d.count), backgroundColor: [COLORS.low, COLORS.ok, COLORS.good, COLORS.great], borderRadius: 8 }] },
    options: { maintainAspectRatio: false, plugins: { ...rtlPlugins, legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0, callback: (v) => nf.format(v) } } } },
  });
  chart("#c-att", {
    type: "doughnut",
    data: { labels: ["حاضر", "تأخیر", "غایب"], datasets: [{ data: [att.present, att.late, att.absent], backgroundColor: [COLORS.great, COLORS.ok, COLORS.low], borderWidth: 0 }] },
    options: { maintainAspectRatio: false, cutout: "62%", plugins: { ...rtlPlugins, legend: { ...rtlPlugins.legend, position: "bottom" } } },
  });
}

/* ---------- students ---------- */
async function students() {
  view.innerHTML = `
  <div class="panel">
    <div class="bar">
      <label>جست‌وجو<input id="q" type="search" placeholder="نام یا کد دانش‌آموزی"></label>
      <label>کلاس<select id="fc"><option value="">همه</option></select></label>
      <label>مرتب‌سازی<select id="fs"><option value="name">نام خانوادگی</option><option value="average">معدل (بیشترین)</option><option value="class">کلاس</option></select></label>
      <span class="spacer"></span>
      <button class="btn" id="add">افزودن دانش‌آموز</button>
    </div>
    <div class="tablewrap"><table><thead><tr><th>کد</th><th>نام</th><th>پایه</th><th>کلاس</th><th>معدل</th><th></th></tr></thead><tbody id="tb"></tbody></table></div>
  </div>`;
  let classes = [];
  const load = guard(async () => {
    const p = new URLSearchParams({ sort: $("#fs").value });
    if ($("#q").value.trim()) p.set("search", $("#q").value.trim());
    if ($("#fc").value) p.set("class_name", $("#fc").value);
    const list = await api("/students?" + p);
    if (!classes.length) {
      classes = [...new Set(list.map((s) => s.class_name))].sort();
      $("#fc").insertAdjacentHTML("beforeend", classes.map((c) => `<option>${esc(c)}</option>`).join(""));
    }
    $("#tb").innerHTML = list.length
      ? list.map((s) => `<tr class="click" data-id="${s.id}"><td>${esc(s.student_code)}</td><td><b>${esc(s.first_name)} ${esc(s.last_name)}</b></td><td>${esc(s.grade_level)}</td><td>${esc(s.class_name)}</td><td>${chip(s.average)}</td>
        <td><button class="btn ghost sm" data-edit="${s.id}">ویرایش</button> <button class="btn danger sm" data-del="${s.id}" data-name="${esc(s.first_name + " " + s.last_name)}">حذف</button></td></tr>`).join("")
      : `<tr><td colspan="6" class="empty">دانش‌آموزی پیدا نشد.</td></tr>`;
    $("#tb").dataset.list = JSON.stringify(list);
  });
  let timer;
  $("#q").addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(load, 250); });
  $("#fc").addEventListener("change", load);
  $("#fs").addEventListener("change", load);
  $("#add").addEventListener("click", () => studentForm(null, load));
  $("#tb").addEventListener("click", guard(async (e) => {
    const list = JSON.parse($("#tb").dataset.list || "[]");
    const edit = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]"), row = e.target.closest("tr[data-id]");
    if (edit) return studentForm(list.find((s) => s.id == edit.dataset.edit), load);
    if (del) {
      if (!confirm(`«${del.dataset.name}» و تمام نمرات و حضور و غیاب او حذف شود؟`)) return;
      await api("/students/" + del.dataset.del, { method: "DELETE" });
      toast("دانش‌آموز حذف شد.");
      return load();
    }
    if (row) report(row.dataset.id);
  }));
  await load();
}

function studentForm(s, done) {
  const v = s || { student_code: "", first_name: "", last_name: "", grade_level: "", class_name: "" };
  openDlg(`
  <div class="dlg-head"><h2>${s ? "ویرایش دانش‌آموز" : "دانش‌آموز جدید"}</h2><button class="btn ghost sm" id="x">بستن</button></div>
  <form id="sf"><div class="formgrid">
    <label>نام<input name="first_name" required maxlength="50" value="${esc(v.first_name)}"></label>
    <label>نام خانوادگی<input name="last_name" required maxlength="50" value="${esc(v.last_name)}"></label>
    <label>کد دانش‌آموزی<input name="student_code" required maxlength="20" value="${esc(v.student_code)}"></label>
    <label>پایه<input name="grade_level" required maxlength="20" placeholder="مثلاً دهم" value="${esc(v.grade_level)}"></label>
    <label class="full">کلاس<input name="class_name" required maxlength="30" placeholder="مثلاً ۱۰-الف" value="${esc(v.class_name)}"></label>
  </div><div class="actions"><button class="btn" type="submit">ذخیره</button><button class="btn ghost" type="button" id="c">انصراف</button></div></form>`);
  $("#x").onclick = $("#c").onclick = closeDlg;
  $("#sf").onsubmit = guard(async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target));
    await api(s ? "/students/" + s.id : "/students", { method: s ? "PUT" : "POST", body });
    closeDlg();
    toast(s ? "تغییرات ذخیره شد." : "دانش‌آموز اضافه شد.");
    done && done();
  });
}

const DIR = { up: "▲ رو به بهبود", down: "▼ کاهشی", flat: "ثابت", insufficient: "داده کافی نیست" };
async function report(id) {
  try {
    const r = await api(`/students/${id}/report`);
    const a = r.attendance;
    openDlg(`
    <div class="dlg-head"><div><h2>${esc(r.student.name)}</h2><small>${esc(r.student.class_name)} • پایه ${esc(r.student.grade_level)} • کد ${esc(r.student.student_code)}</small></div><button class="btn ghost sm" id="x">بستن</button></div>
    <div class="strip" style="grid-template-columns:repeat(3,1fr)">
      <div><span>معدل</span><b>${num(r.average)}</b></div>
      <div><span>درصد حضور</span><b>${a.rate == null ? "—" : num(a.rate) + "٪"}</b></div>
      <div><span>غیبت</span><b>${num(a.absent)}</b><em>${num(a.late)} تأخیر</em></div>
    </div>
    ${r.subjects.length ? `<div class="chartbox mt" style="height:230px"><canvas id="rc"></canvas></div>
    <table class="mt"><thead><tr><th>درس</th><th>میانگین</th><th>تعداد نمره</th><th>روند</th></tr></thead><tbody>
      ${r.subjects.map((x) => `<tr><td>${esc(x.name)}</td><td>${chip(x.average)}</td><td>${num(x.count)}</td><td>${DIR[x.direction]}</td></tr>`).join("")}</tbody></table>
    <h2 class="mt">یافته‌ها</h2>
    ${r.insights.length ? `<ul class="insights">${r.insights.map((t) => `<li>${esc(t)}</li>`).join("")}</ul>` : `<p>مورد قابل‌توجهی دیده نشد.</p>`}
    <p class="note mt">این یافته‌ها فقط بر پایه نمرات ثبت‌شده‌اند و پیش‌بینی قطعی از توانایی دانش‌آموز نیستند.</p>`
    : `<p class="empty">برای این دانش‌آموز هنوز نمره‌ای ثبت نشده است.</p>`}`);
    $("#x").onclick = closeDlg;
    if (r.subjects.length) {
      const labels = [...new Set(r.subjects.flatMap((s) => s.points.map((p) => p.date)))].sort();
      const palette = RAINBOW;
      dlgChart = new Chart($("#rc"), {
        type: "line",
        data: { labels: labels.map(dshort), datasets: r.subjects.map((s, i) => ({ label: s.name, borderColor: palette[i % 6], backgroundColor: palette[i % 6], tension: 0.25, spanGaps: true, pointRadius: 3, data: labels.map((d) => (s.points.find((p) => p.date === d) || {}).score ?? null) })) },
        options: { maintainAspectRatio: false, plugins: rtlPlugins, scales: { y: { min: 0, max: 20, ticks: { callback: (v) => nf.format(v) } } } },
      });
    }
  } catch (e) { toast(e.message, true); }
}

/* ---------- grades ---------- */
async function grades() {
  const [st, sb] = await Promise.all([api("/students?sort=name"), api("/subjects")]);
  const opts = (arr, f) => arr.map((x) => `<option value="${x.id}">${esc(f(x))}</option>`).join("");
  if (!st.length) { view.innerHTML = empty("ابتدا دانش‌آموز ثبت کنید."); return; }
  view.innerHTML = `
  <div class="panel">
    <h2>ثبت نمره جدید</h2>
    <form class="bar" id="gf">
      <label>دانش‌آموز<select name="student_id" required>${opts(st, (s) => `${s.last_name} ${s.first_name} (${s.class_name})`)}</select></label>
      <label>درس<select name="subject_id" id="gs" required>${opts(sb, (s) => s.name)}</select></label>
      <label>نمره (از ۲۰)<input name="score" type="number" min="0" max="20" step="0.25" required style="width:100px"></label>
      <label>تاریخ<input name="exam_date" type="date" value="${todayISO()}" required></label>
      <label>عنوان آزمون<input name="title" maxlength="100" placeholder="اختیاری"></label>
      <button class="btn" type="submit">ثبت نمره</button>
      <button class="btn ghost" type="button" id="ns">درس جدید</button>
    </form>
  </div>
  <div class="panel mt">
    <div class="bar">
      <label>فیلتر دانش‌آموز<select id="fst"><option value="">همه</option>${opts(st, (s) => `${s.last_name} ${s.first_name}`)}</select></label>
      <label>فیلتر درس<select id="fsb"><option value="">همه</option>${opts(sb, (s) => s.name)}</select></label>
    </div>
    <div class="tablewrap"><table><thead><tr><th>تاریخ</th><th>دانش‌آموز</th><th>درس</th><th>عنوان</th><th>نمره</th><th></th></tr></thead><tbody id="gt"></tbody></table></div>
    <p class="note mt">آخرین ۲۰۰ نمره نمایش داده می‌شود.</p>
  </div>`;
  const load = guard(async () => {
    const p = new URLSearchParams();
    if ($("#fst").value) p.set("student_id", $("#fst").value);
    if ($("#fsb").value) p.set("subject_id", $("#fsb").value);
    const list = await api("/grades?" + p);
    $("#gt").innerHTML = list.length
      ? list.map((g) => `<tr><td>${dlong(g.exam_date)}</td><td>${esc(g.student_name)}</td><td>${esc(g.subject_name)}</td><td>${esc(g.title)}</td><td>${chip(g.score)}</td><td><button class="btn danger sm" data-del="${g.id}">حذف</button></td></tr>`).join("")
      : `<tr><td colspan="6" class="empty">نمره‌ای ثبت نشده است.</td></tr>`;
  });
  $("#fst").onchange = $("#fsb").onchange = load;
  $("#gf").onsubmit = guard(async (e) => {
    e.preventDefault();
    const body = Object.fromEntries(new FormData(e.target));
    body.student_id = +body.student_id; body.subject_id = +body.subject_id; body.score = +body.score;
    await api("/grades", { method: "POST", body });
    toast("نمره ثبت شد.");
    e.target.score.value = ""; e.target.title.value = "";
    load();
  });
  $("#gt").onclick = guard(async (e) => {
    const b = e.target.closest("[data-del]");
    if (!b || !confirm("این نمره حذف شود؟")) return;
    await api("/grades/" + b.dataset.del, { method: "DELETE" });
    toast("نمره حذف شد.");
    load();
  });
  $("#ns").onclick = () => {
    openDlg(`
    <div class="dlg-head"><h2>درس جدید</h2><button class="btn ghost sm" id="x">بستن</button></div>
    <form id="sbf"><label>نام درس<input id="sbn" required maxlength="60" placeholder="مثلاً شیمی" autofocus></label>
    <div class="actions"><button class="btn" type="submit">افزودن درس</button><button class="btn ghost" type="button" id="c">انصراف</button></div></form>`);
    $("#x").onclick = $("#c").onclick = closeDlg;
    $("#sbf").onsubmit = guard(async (e) => {
      e.preventDefault();
      const name = $("#sbn").value.trim();
      if (!name) return;
      const sub = await api("/subjects", { method: "POST", body: { name } });
      closeDlg();
      toast("درس «" + sub.name + "» اضافه شد.");
      $("#gs").insertAdjacentHTML("beforeend", `<option value="${sub.id}">${esc(sub.name)}</option>`);
      $("#gs").value = sub.id;
      $("#fsb").insertAdjacentHTML("beforeend", `<option value="${sub.id}">${esc(sub.name)}</option>`);
    });
  };
  await load();
}

/* ---------- attendance ---------- */
async function attendance() {
  const all = await api("/students?sort=class");
  if (!all.length) { view.innerHTML = empty("ابتدا دانش‌آموز ثبت کنید."); return; }
  const classes = [...new Set(all.map((s) => s.class_name))];
  view.innerHTML = `
  <div class="panel">
    <div class="bar">
      <label>کلاس<select id="ac">${classes.map((c) => `<option>${esc(c)}</option>`).join("")}</select></label>
      <label>تاریخ<input id="ad" type="date" value="${todayISO()}"></label>
      <span class="spacer"></span>
      <button class="btn ghost" id="allp">همه حاضر</button>
      <button class="btn" id="save">ذخیره حضور و غیاب</button>
    </div>
    <div class="tablewrap"><table><thead><tr><th>دانش‌آموز</th><th>وضعیت</th></tr></thead><tbody id="at"></tbody></table></div>
  </div>`;
  const load = guard(async () => {
    const cls = $("#ac").value, day = $("#ad").value;
    if (!day) return;
    const saved = Object.fromEntries((await api(`/attendance?day=${day}&class_name=${encodeURIComponent(cls)}`)).map((r) => [r.student_id, r.status]));
    $("#at").innerHTML = all.filter((s) => s.class_name === cls).map((s) => {
      const cur = saved[s.id] || "present";
      const r = (val, cls2, text) => `<label class="${cls2}"><input type="radio" name="s${s.id}" value="${val}" ${cur === val ? "checked" : ""}>${text}</label>`;
      return `<tr data-id="${s.id}"><td>${esc(s.last_name)} ${esc(s.first_name)}</td><td><div class="seg">${r("present", "p", "حاضر")}${r("late", "l", "تأخیر")}${r("absent", "a", "غایب")}</div></td></tr>`;
    }).join("");
  });
  $("#ac").onchange = $("#ad").onchange = load;
  $("#allp").onclick = () => document.querySelectorAll('#at input[value="present"]').forEach((i) => (i.checked = true));
  $("#save").onclick = guard(async () => {
    const records = [...document.querySelectorAll("#at tr")].map((tr) => ({ student_id: +tr.dataset.id, status: tr.querySelector("input:checked").value }));
    if (!records.length || !$("#ad").value) return toast("کلاس و تاریخ را انتخاب کنید.", true);
    await api("/attendance", { method: "POST", body: { day: $("#ad").value, records } });
    toast("حضور و غیاب ذخیره شد.");
  });
  await load();
}

go("dashboard");
