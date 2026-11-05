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

      ws.send(JSON.stringify({
        id: n,
        method,
        params
      }));
    });
  }

  const r = await call("Runtime.evaluate", {
    expression: `
      JSON.stringify(
        [...document.querySelectorAll("video")].map((v, i) => {
          let host = null;
          let protocol = null;

          try {
            const u = new URL(v.currentSrc || v.src);
            host = u.host;
            protocol = u.protocol;
          } catch {}

          return {
            index: i,
            has_src: !!(v.currentSrc || v.src),
            host,
            protocol,
            duration: Number.isFinite(v.duration) ? v.duration : null,
            ready_state: v.readyState,
            network_state: v.networkState,
            paused: v.paused,
            has_poster: !!v.poster
          };
        })
      )
    `,
    returnByValue: true
  });

  const videos = JSON.parse(r.result.value || "[]");

  ws.close();

  console.log("VIDEO_COUNT=" + videos.length);

  videos.forEach(v => {
    console.log(JSON.stringify(v));
  });

  if (videos.some(v => v.has_src)) {
    console.log("SM3_09C3_G1_MEDIA_SOURCE_VISIBLE_PASS");
  } else {
    console.log("SM3_09C3_G1_MEDIA_SOURCE_NOT_VISIBLE");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
