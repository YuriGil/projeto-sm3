const base = "http://127.0.0.1:9222";

async function main() {
  const targets = await fetch(base + "/json/list").then(r => r.json());

  const page = targets.find(
    t =>
      t.type === "page" &&
      typeof t.url === "string" &&
      t.url.includes("instagram.com/fredao_oliveira")
  );

  if (!page) {
    throw new Error("SM3_INSTAGRAM_PROFILE_TAB_NOT_FOUND");
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
        [...document.querySelectorAll('a[href]')]
          .map(a => a.href)
          .filter(h =>
            h.includes('/reel/') ||
            h.includes('/reels/') ||
            h.includes('/p/')
          )
          .filter((v, i, a) => a.indexOf(v) === i)
          .slice(0, 30)
      )
    `,
    returnByValue: true
  });

  const links = JSON.parse(r.result.value || "[]");

  console.log("CONTENT_LINK_COUNT=" + links.length);

  links.forEach((link, i) => {
    console.log(
      String(i + 1).padStart(2, "0") +
      " " +
      link
    );
  });

  ws.close();

  if (links.length > 0) {
    console.log("SM3_09C3_F6_CONTENT_DISCOVERY_PASS");
  } else {
    console.log("SM3_09C3_F6_NO_CONTENT_LINKS");
  }
}

main().catch(e => {
  console.error(e);
  process.exit(1);
});
