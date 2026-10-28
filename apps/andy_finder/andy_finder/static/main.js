const $ = (id) => document.getElementById(id);
async function refresh() {
  try {
    const s = await (await fetch("/status")).json();
    $("status").textContent = s.status; $("where").textContent = s.where;
    document.querySelector("button").disabled = s.busy;
  } catch (e) { $("status").textContent = "The app isn't answering."; }
}
$("ask").onsubmit = async (e) => {
  e.preventDefault();
  await fetch("/find", { method: "POST", headers: { "Content-Type": "application/json" },
                         body: JSON.stringify({ thing: $("thing").value }) });
  refresh();
};
setInterval(refresh, 700); refresh();
