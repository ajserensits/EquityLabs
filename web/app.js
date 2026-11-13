const status = document.querySelector("#api-status");

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const payload = await response.json();
  if (!response.ok) throw new Error(payload.error?.message || `Request failed (${response.status})`);
  return payload.data;
}

function formObject(form) {
  return Object.fromEntries(
    [...new FormData(form).entries()]
      .filter(([key, value]) => key !== "file" && value !== "")
  );
}

function show(target, value) {
  target.textContent = typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

api("/api/health")
  .then(() => { status.textContent = "API ready"; status.classList.add("ready"); })
  .catch((error) => { status.textContent = error.message; });

document.querySelector("#earnings-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const output = document.querySelector("#earnings-result");
  try {
    const result = await api("/api/valuation/earnings", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formObject(event.currentTarget)),
    });
    show(output, result);
  } catch (error) { show(output, error.message); }
});

document.querySelector("#dcf-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const output = document.querySelector("#dcf-result");
  try {
    const result = await api("/api/valuation/dcf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(formObject(event.currentTarget)),
    });
    show(output, result);
  } catch (error) { show(output, error.message); }
});

document.querySelector("#price-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const output = document.querySelector("#price-result");
  const values = new FormData(event.currentTarget);
  const file = values.get("file");
  if (!(file instanceof File)) return;
  const query = new URLSearchParams({ symbol: values.get("symbol"), source: values.get("source") });
  try {
    const result = await api(`/api/prices/import?${query}`, {
      method: "POST", headers: { "Content-Type": "text/csv" }, body: await file.text(),
    });
    show(output, result);
  } catch (error) { show(output, error.message); }
});
