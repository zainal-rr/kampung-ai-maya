async function refresh() {
  const state = document.getElementById("state");
  const badge = await chrome.action.getBadgeText({});
  const connected = badge === "ON" || badge === "RUN";
  state.textContent = connected ? "connected" : "not connected";
  state.className = connected ? "ok" : "bad";
}

document.getElementById("save").addEventListener("click", async () => {
  const token = document.getElementById("token").value.trim();
  await chrome.storage.local.set({ token });
  chrome.runtime.reload();
});

chrome.storage.local.get("token").then(({ token }) => {
  if (token) document.getElementById("token").value = token;
});
refresh();
setInterval(refresh, 1500);
