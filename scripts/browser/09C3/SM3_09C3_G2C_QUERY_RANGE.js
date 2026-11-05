const CDP = "http://127.0.0.1:9222";

async function main() {
  const targets = await fetch(CDP + "/json/list").then(r => r.json());

  const page = targets.find(
    t =>
      t.type === "page" &&
      typeof t.url === "string" &&
      t.url.includes("/reel/DdW4KBZhpEd")
  );

  if (!page) throw new Error("SM3_REEL_TAB_NOT_FOUND");

  const ws = new WebSocket(page.webSocketDebuggerUrl);

  let id = 0;
  const pending = new Map();
  const media = [];

  ws.onmessage = e => {
    const m = JSON.parse(e.data);

    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id);
      pending.delete(m.id);

      if (m.error) p.reject(m.error);
      else p.resolve(m.result);

      return;
    }

    if (m.method !== "Network.responseReceived") return;

    const r = m.params.response || {};

    if (
      !String(r.mimeType || "")
        .toLowerCase()
        .startsWith("video/")
    ) return;

    try {
      const u = new URL(r.url);

      const names = [...u.searchParams.keys()]
        .filter((v, i, a) => a.indexOf(v) === i)
        .sort();

      media.push({
        host: u.host,
        path: u.pathname,
        status: r.status,
        mimeType: r.mimeType,
        parameterNames: names,

        bytestart:
          u.searchParams.get("bytestart") ??
          u.searchParams.get("byte_start"),

        byteend:
          u.searchParams.get("byteend") ??
          u.searchParams.get("byte_end")
      });
    } catch {}
  };

  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const n = ++id;

      pending.set(n, { resolve, reject });

      ws.send(JSON.stringify({
        id: n,
        method,
        params
      }));
    });
  }

  await call("Network.enable");
  await call("Page.enable");

  console.log("RELOADING_FOR_QUERY_ANALYSIS=true");

  await call("Page.reload", {
    ignoreCache: false
  });

  await new Promise(resolve =>
    setTimeout(resolve, 8000)
  );

  ws.close();

  console.log("VIDEO_RESPONSE_COUNT=" + media.length);

  media.forEach((x, i) => {
    console.log("");
    console.log("VIDEO_" + String(i + 1).padStart(2, "0"));

    console.log(JSON.stringify({
      host: x.host,
      path: x.path,
      status: x.status,
      mimeType: x.mimeType,
      parameterNames: x.parameterNames,
      bytestart: x.bytestart,
      byteend: x.byteend
    }, null, 2));
  });

  const ranged = media.filter(
    x => x.bytestart !== null || x.byteend !== null
  );

  console.log("");
  console.log("URL_RANGE_REQUESTS=" + ranged.length);

  if (ranged.length > 0) {
    console.log("SM3_09C3_G2C_URL_BYTE_RANGE_PASS");
  } else {
    console.log("SM3_09C3_G2C_NO_URL_BYTE_RANGE");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
