// Andy Finder's page: what Andy sees while it looks, the find as a reveal, and the finds lately. It asks /status
// about twice a second; the camera picture comes from /frame.jpg only while there is one (a search, or a find).
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";
const THINGS = ["glasses", "keys", "phone", "remote", "wallet", "mug", "watch"];
const VIEW_NAMES = ["middle", "left", "right", "far left", "far right"];
let last = null, frameV = -1, revealed = "";

function make(tag, attrs, cls) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  if (cls) e.setAttribute("class", cls);
  return e;
}
async function ask(thing) {
  if (!thing || (last && last.busy)) return;
  $("thing").value = thing;
  revealed = "";
  await fetch("/find", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ thing }) });
  refresh();
}
for (const t of THINGS) {
  const b = document.createElement("button"); b.type = "button"; b.textContent = t; b.onclick = () => ask(t); $("chips").append(b);
}
$("ask").onsubmit = (e) => { e.preventDefault(); ask($("thing").value.trim()); };

function marks(w, h, boxes, found) {  // the candidates SAM 3.1 outlined, or the found thing with a spotlight
  const svg = $("marks"); svg.replaceChildren();
  if (!w || !h) return;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  if (found) {
    const [l, t, r, b] = found.box, pad = Math.max(10, (r - l) * 0.12);
    const m = make("mask", { id: "spot" });
    m.append(make("rect", { width: w, height: h, fill: "white" }),
             make("rect", { x: l - pad, y: t - pad, width: r - l + 2 * pad, height: b - t + 2 * pad, rx: pad, fill: "black" }));
    const defs = make("defs"); defs.append(m);
    svg.append(defs, make("rect", { width: w, height: h, mask: "url(#spot)" }, "dim"),
               make("rect", { x: l, y: t, width: r - l, height: b - t, rx: 6, pathLength: 1 }, "edge"));
    return;
  }
  for (const [l, t, r, b] of boxes) svg.append(make("rect", { x: l, y: t, width: r - l, height: b - t, rx: 6 }, "cand"));
}

function eyesTo(yaw) {  // Andy's left is the viewer's right: the face's eyes go where the head is turning
  const x = Math.max(-1, Math.min(1, (yaw || 0) / 55)) * 30;
  for (const e of document.querySelectorAll(".eyes")) e.setAttribute("style", `transform: translate(${x}px, 4px)`);
}
(function blink() {
  document.body.classList.add("blink"); setTimeout(() => document.body.classList.remove("blink"), 130);
  setTimeout(blink, 2500 + Math.random() * 3500);
})();

function render(s) {
  last = s;
  const view = $("view"), phase = s.phase || "ready";
  view.className = "eye-view " + phase;
  $("go").disabled = s.busy;
  document.querySelectorAll("#chips button").forEach((b) => (b.disabled = s.busy));
  $("where").textContent = s.local ? "Pictures stay on this computer" : "Pictures go to Meta's Model API";
  $("where").classList.toggle("cloud", !s.local);
  $("where-long").textContent = "Where the pictures go: " + s.where + ".";
  $("status").textContent = s.status;

  if (s.frame_v !== frameV) {  // a new picture (or none): fetched once
    frameV = s.frame_v;
    const photo = $("photo");
    photo.onload = () => view.querySelector(".stage").parentElement.classList.add("has-photo");
    photo.onerror = () => view.classList.remove("has-photo");
    photo.src = "/frame.jpg?v=" + frameV;
  }
  const hasPhoto = phase === "looking" || phase === "found";
  view.classList.toggle("has-photo", hasPhoto && $("photo").complete && $("photo").naturalWidth > 0);

  if (phase === "looking" && s.look) {
    eyesTo(s.look.yaw);
    $("scan-text").textContent = `Looking ${s.look.side} · ${s.look.boxes.length ? s.look.boxes.length + " possible" : "nothing yet"}`;
    marks(s.look.w, s.look.h, s.look.boxes, null);
  } else if (phase === "found" && s.found) {
    eyesTo(s.found.yaw);
    const key = s.found.thing + s.found.seconds + s.found.box.join(",");
    if (key !== revealed) {  // the reveal plays once per find
      revealed = key;
      marks(s.found.w, s.found.h, [], s.found);
      $("r-title").textContent = "Your " + s.found.thing;
      const nums = $("r-nums"); nums.replaceChildren();
      $("r-side").textContent = s.found.side[0].toUpperCase() + s.found.side.slice(1) + ".";
      for (const [big, small] of [[s.found.seconds.toFixed(1) + " s", "to find it"], [Math.round(s.found.score * 100) + "%", "SAM 3.1 sure"]]) {
        const d = document.createElement("div"), b = document.createElement("b"), sp = document.createElement("span");
        b.textContent = big; sp.textContent = small; d.append(b, sp); nums.append(d);
      }
      // restart the reveal's animations
      for (const el of document.querySelectorAll(".reveal > *")) { el.style.animation = "none"; void el.offsetWidth; el.style.animation = ""; }
    }
  }
  $("idle-title").textContent = phase === "missing" ? "Not in view." : "I'm ready.";
  $("idle-line").textContent = phase === "missing" ? "It may be somewhere I can't look: behind me, or under something."
                                                    : "Tap a thing, or type one.";
  if (phase !== "looking" && phase !== "found") {
    eyesTo(phase === "missing" ? (Date.now() / 600 % 2 < 1 ? -40 : 40) : 0);  // looking about, when it couldn't see it
    marks(0, 0, [], null);
  }

  const views = $("views"); views.replaceChildren();
  VIEW_NAMES.forEach((name, i) => {
    const v = (s.views || [])[i], li = document.createElement("li");
    if (v && v.done) li.className = v.best >= 0.75 ? "done hit" : "done";
    if (phase === "looking" && s.look && s.look.view === i) li.className = "now";
    li.append(document.createElement("i"), name); views.append(li);
  });

  $("recent").hidden = !(s.history && s.history.length);
  $("history").replaceChildren(...(s.history || []).map((h) => {
    const li = document.createElement("li"), b = document.createElement("button"), when = document.createElement("span");
    const mins = Math.round((Date.now() / 1000 - h.at) / 60);
    when.textContent = `${h.side} · ${mins < 1 ? "just now" : mins + " min ago"}`;
    b.type = "button"; b.append(h.thing, when); b.onclick = () => ask(h.thing); li.append(b); return li;
  }));
}

async function refresh() {
  try { render(await (await fetch("/status", { cache: "no-store" })).json()); }
  catch (e) { $("status").textContent = "The app isn't answering."; }
}
setInterval(refresh, 450); refresh();
