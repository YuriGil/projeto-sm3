const base = "http://127.0.0.1:9222";

async function main() {
  const targets = await fetch(base + "/json/list").then(r => r.json());

  const page = targets.find(
    t => t.type === "page" && t.webSocketDebuggerUrl
  );

  if (!page) throw new Error("SM3_CDP_NO_PAGE_TARGET");

  console.log("TARGET_TYPE=" + page.type);
  console.log("TARGET_URL_FROM_LIST=" + page.url);

  const ws = new WebSocket(page.webSocketDebuggerUrl);

  let id = 0;
  const pending = new Map();

  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    if (!m.id || !pending.has(m.id)) return;

    const p = pending.get(m.id);
    pending.delete(m.id);

    if (m.error) p.reject(m.error);
    else p.resolve(m.result);
  };

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const n = ++id;
      pending.set(n, { resolve, reject });
      ws.send(JSON.stringify({ id: n, method, params }));
    });
  }

  const r = await call("Runtime.evaluate", {
    expression: `JSON.stringify({
      title: document.title,
      url: location.href,
      readyState: document.readyState
    })`,
    returnByValue: true
  });

  const x = JSON.parse(r.result.value);

  console.log("TITLE=" + x.title);
  console.log("URL=" + x.url);
  console.log("READY_STATE=" + x.readyState);

  ws.close();

  console.log("SM3_09C3_F3_CDP_CHANNEL_PASS");
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
