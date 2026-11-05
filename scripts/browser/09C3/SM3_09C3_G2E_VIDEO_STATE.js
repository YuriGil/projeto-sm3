const CDP = "http://127.0.0.1:9222";

async function main() {
  const targets = await fetch(CDP + "/json/list").then(r => r.json());

  const page = targets.find(
    x =>
      x.type === "page" &&
      typeof x.url === "string" &&
      x.url.includes("/reel/DdW4KBZhpEd")
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

  const result = await call("Runtime.evaluate", {
    expression: `
      (() => {
        const v = document.querySelector("video");

        if (!v) {
          return {
            videoFound: false
          };
        }

        return {
          videoFound: true,
          duration: Number.isFinite(v.duration) ? v.duration : null,
          currentTime: v.currentTime,
          ended: v.ended,
          paused: v.paused,
          loop: v.loop,
          autoplay: v.autoplay,
          readyState: v.readyState
        };
      })()
    `,
    returnByValue: true
  });

  const state = result?.result?.value;

  console.log("VIDEO_STATE:");
  console.log(JSON.stringify(state, null, 2));

  ws.close();

  if (state?.videoFound) {
    console.log("SM3_09C3_G2E_VIDEO_STATE_PASS");
  } else {
    console.log("SM3_09C3_G2E_VIDEO_NOT_FOUND");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
