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
  const reqs = new Map();

  function header(obj, name) {
    const key = Object.keys(obj || {}).find(
      k => k.toLowerCase() === name.toLowerCase()
    );
    return key ? String(obj[key]) : null;
  }

  function safeUrl(raw) {
    try {
      const u = new URL(raw);
      return {
        host: u.host,
        path: u.pathname
      };
    } catch {
      return { host: null, path: null };
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

    if (m.method === "Network.requestWillBeSent") {
      const p = m.params;
      const r = p.request || {};

      reqs.set(p.requestId, {
        requestId: p.requestId,
        type: p.type || null,
        url: r.url,
        requestRange: header(r.headers, "range"),
        status: null,
        mimeType: null,
        contentLength: null,
        contentRange: null,
        acceptRanges: null,
        finishedBytes: null,
        failed: false
      });
    }

    if (m.method === "Network.responseReceived") {
      const p = m.params;
      const r = p.response || {};

      const mime = String(r.mimeType || "").toLowerCase();
      const htype = String(
        header(r.headers, "content-type") || ""
      ).toLowerCase();

      const looksMedia =
        mime.startsWith("video/") ||
        mime.startsWith("audio/") ||
        htype.startsWith("video/") ||
        htype.startsWith("audio/");

      if (!looksMedia) return;

      const rec = reqs.get(p.requestId) || {
        requestId: p.requestId,
        url: r.url
      };

      rec.type = p.type || rec.type || null;
      rec.url = r.url;
      rec.status = r.status;
      rec.mimeType = r.mimeType || null;
      rec.contentLength = header(r.headers, "content-length");
      rec.contentRange = header(r.headers, "content-range");
      rec.acceptRanges = header(r.headers, "accept-ranges");
      rec.isMedia = true;

      reqs.set(p.requestId, rec);
    }

    if (m.method === "Network.loadingFinished") {
      const rec = reqs.get(m.params.requestId);

      if (rec) {
        rec.finishedBytes = m.params.encodedDataLength;
      }
    }

    if (m.method === "Network.loadingFailed") {
      const rec = reqs.get(m.params.requestId);

      if (rec) {
        rec.failed = true;
        rec.errorText = m.params.errorText || null;
      }
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

  console.log("RELOADING_REEL_FOR_TRANSFER_ANALYSIS=true");

  await call("Page.reload", {
    ignoreCache: false
  });

  await new Promise(resolve =>
    setTimeout(resolve, 10000)
  );

  ws.close();

  const media = [...reqs.values()]
    .filter(x => x.isMedia)
    .map(x => {
      const safe = safeUrl(x.url);

      return {
        requestId: x.requestId,
        type: x.type,
        status: x.status,
        mimeType: x.mimeType,
        host: safe.host,
        path: safe.path,
        requestRange: x.requestRange,
        contentRange: x.contentRange,
        contentLength: x.contentLength,
        acceptRanges: x.acceptRanges,
        finishedBytes: x.finishedBytes,
        failed: x.failed
      };
    });

  console.log("MEDIA_REQUEST_COUNT=" + media.length);

  media.forEach((x, i) => {
    console.log("");
    console.log("MEDIA_" + String(i + 1).padStart(2, "0"));
    console.log(JSON.stringify(x, null, 2));
  });

  const completed = media.filter(
    x =>
      x.status >= 200 &&
      x.status < 400 &&
      x.failed !== true &&
      Number(x.finishedBytes || 0) > 0
  );

  console.log("");
  console.log("COMPLETED_MEDIA_REQUESTS=" + completed.length);

  if (completed.length > 0) {
    console.log("SM3_09C3_G2B_MEDIA_TRANSFER_ANALYSIS_PASS");
  } else {
    console.log("SM3_09C3_G2B_MEDIA_TRANSFER_ANALYSIS_NO_COMPLETE_MEDIA");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
