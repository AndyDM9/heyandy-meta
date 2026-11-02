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
$("ring").onclick = async () => {  // Ring it: Reachy listens while you call your phone, then turns to the ringing
  if (last && last.busy) return;
  revealed = "";
  await fetch("/ring", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ thing: "phone" }) });
  refresh();
};

function sonar(s) {  // seen from above, front up: each turn of the head, the side it heard the ringing on, then where it is
  const svg = $("sonar-svg"), R = 100, snd = s.sound || { steps: [] }; svg.replaceChildren();
  const at = (yaw, r) => [-Math.sin(yaw * Math.PI / 180) * r, -Math.cos(yaw * Math.PI / 180) * r];  // its left on the left
  for (const r of [R, R * 0.66, R * 0.33]) svg.append(make("circle", { cx: 0, cy: 0, r }, "ring-line"));
  snd.steps.forEach(([yaw, heard], i) => {
    const [x, y] = at(yaw, R), now = i === snd.steps.length - 1;
    svg.append(make("line", { x1: 0, y1: 0, x2: x, y2: y }, now ? "turn now" : "turn"));
    const [mx, my] = at(yaw + (heard > 0 ? 12 : heard < 0 ? -12 : 0), R * 0.82);
    svg.append(make("circle", { cx: mx, cy: my, r: now ? 6 : 4 }, now ? "heard now" : "heard"));
  });
  if (snd.facing != null) {
    const [x, y] = at(snd.facing, R * 0.86);
    for (let i = 0; i < 3; i++) svg.append(make("circle", { cx: x, cy: y, r: 10, style: `animation-delay: ${i * 0.6}s` }, "wave"));
    svg.append(make("circle", { cx: x, cy: y, r: 9 }, "source"));
  } else if (s.phase === "listening") svg.append(make("circle", { cx: 0, cy: 0, r: 22 }, "listen"));
  svg.append(make("rect", { x: -16, y: -9, width: 32, height: 18, rx: 9 }, "robot"));
  svg.append(make("ellipse", { cx: -7, cy: 0, rx: 2.2, ry: 4.4 }, "eye2"), make("ellipse", { cx: 7, cy: 0, rx: 2.2, ry: 4.4 }, "eye2"));
  const waiting = snd.waiting != null && !snd.steps.length;
  $("sonar-title").textContent = s.phase === "unheard" ? "I didn't hear it ring." : s.phase === "heard" ? "It's ringing over there."
                               : waiting ? "Call your phone now." : "I hear it. Turning to the sound.";
  $("sonar-line").textContent = s.phase === "unheard" ? "Is the ringer on? Tap Ring it and call again."
                              : s.phase === "heard" ? s.status
                              : waiting ? `I'm listening (${snd.waiting} s). Its own microphones; nothing is recorded.`
                              : "It turns until it hears the ringing straight ahead.";
}

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
  $("go").disabled = s.busy; $("ring").disabled = s.busy;
  $("ring").textContent = phase === "listening" ? "Listening…" : "Ring it";
  if (["listening", "heard", "unheard"].includes(phase)) { sonar(s); eyesTo(s.sound && s.sound.steps.length ? s.sound.steps.at(-1)[0] : 0); }
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
    $("scan-text").textContent = s.look.pointing ? "Found it · turning to it, then checking my aim"
      : `Looking ${s.look.side} · ${s.look.boxes.length ? s.look.boxes.length + " possible" : "nothing yet"}`;
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
      const figures = [[s.found.seconds.toFixed(1) + " s", "to find it"], [Math.round(s.found.score * 100) + "%", "SAM 3.1 sure"]];
      if (s.found.aim != null) figures.push([s.found.aim.toFixed(1) + "°", "off, as my camera checked"]);
      for (const [big, small] of figures) {
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
  if (!["looking", "found", "listening", "heard", "unheard"].includes(phase)) {
    eyesTo(phase === "missing" ? (Date.now() / 600 % 2 < 1 ? -40 : 40) : 0);  // looking about, when it couldn't see it
    marks(0, 0, [], null);
  }

  const views = $("views"); views.replaceChildren();
  const named = (v, i) => !v ? VIEW_NAMES[i] : Math.abs(v.yaw) < 10 ? "middle" : (Math.abs(v.yaw) > 40 ? "far " : "") + (v.yaw > 0 ? "left" : "right");
  (s.views && s.views.length ? s.views : VIEW_NAMES).forEach((_, i) => {  // each view by where it really looked
    const v = (s.views || [])[i], li = document.createElement("li"), name = named(v, i);
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
