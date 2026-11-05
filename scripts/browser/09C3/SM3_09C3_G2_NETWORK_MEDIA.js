const CDP = "http://127.0.0.1:9222";

async function main() {
  const targets = await fetch(CDP + "/json/list").then(r => r.json());

  const page = targets.find(
    t =>
      t.type === "page" &&
      typeof t.url === "string" &&
      t.url.includes("/reel/DdW4KBZhpEd")
  );

  if (!page) {
    throw new Error("SM3_REEL_TAB_NOT_FOUND");
  }

  const ws = new WebSocket(page.webSocketDebuggerUrl);

  let id = 0;
  const pending = new Map();
  const media = [];

  function safeUrl(raw) {
    try {
      const u = new URL(raw);

      return {
        host: u.host,
        path: u.pathname
      };
    } catch {
      return {
        host: null,
        path: null
      };
    }
  }

  ws.onmessage = e => {
    const m = JSON.parse(e.data);

    if (m.id && pending.has(m.id)) {
      const p = pending.get(m.id);
      pending.delete(m.id);

      if (m.error) p.reject(m.error);
      else p.resolve(m.result);

      return;
    }

    if (m.method === "Network.responseReceived") {
      const r = m.params.response;

      const contentType =
        (r.mimeType || "").toLowerCase();

      const headers = r.headers || {};

      const headerType =
        String(
          headers["content-type"] ||
          headers["Content-Type"] ||
          ""
        ).toLowerCase();

      const looksMedia =
        contentType.startsWith("video/") ||
        contentType.startsWith("audio/") ||
        headerType.startsWith("video/") ||
        headerType.startsWith("audio/");

      if (!looksMedia) return;

      const safe = safeUrl(r.url);

      media.push({
        requestId: m.params.requestId,
        status: r.status,
        mimeType: r.mimeType,
        host: safe.host,
        path: safe.path,
        encodedDataLength: r.encodedDataLength || 0
      });
    }
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

  console.log("RELOADING_REEL_FOR_NETWORK_CAPTURE=true");

  await call("Page.reload", {
    ignoreCache: false
  });

  await new Promise(resolve =>
    setTimeout(resolve, 8000)
  );

  ws.close();

  const unique = [
    ...new Map(
      media.map(x => [
        `${x.host}|${x.path}|${x.mimeType}`,
        x
      ])
    ).values()
  ];

  console.log("MEDIA_RESPONSE_COUNT=" + unique.length);

  unique.forEach((x, i) => {
    console.log(
      JSON.stringify({
        index: i,
        status: x.status,
        mimeType: x.mimeType,
        host: x.host,
        path: x.path,
        encodedDataLength: x.encodedDataLength
      })
    );
  });

  if (unique.length > 0) {
    console.log("SM3_09C3_G2_NETWORK_MEDIA_DISCOVERY_PASS");
  } else {
    console.log("SM3_09C3_G2_NETWORK_MEDIA_DISCOVERY_NO_MATCH");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
