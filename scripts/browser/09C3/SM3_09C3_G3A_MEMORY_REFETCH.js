const crypto = require("node:crypto");

const CDP = "http://127.0.0.1:9222";
const sleep = ms => new Promise(r => setTimeout(r, ms));

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
  const candidates = [];

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
    ) {
      return;
    }

    try {

      const u = new URL(r.url);

      const start = Number(
        u.searchParams.get("bytestart")
      );

      const end = Number(
        u.searchParams.get("byteend")
      );

      if (
        !Number.isFinite(start) ||
        !Number.isFinite(end) ||
        end < start
      ) {
        return;
      }

      candidates.push({
        url: r.url,
        host: u.host,
        path: u.pathname,
        start,
        end,
        expectedBytes: end - start + 1
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

      pending.set(n, {
        resolve,
        reject
      });

      ws.send(JSON.stringify({
        id: n,
        method,
        params
      }));
    });
  }

  await call("Network.enable");
  await call("Page.enable");
  await call("Runtime.enable");

  console.log("RELOADING_REEL=true");

  await call("Page.reload", {
    ignoreCache: true
  });


  // --------------------------------------------------------
  // ESPERAR O VIDEO EXISTIR
  // --------------------------------------------------------

  let videoReady = false;

  for (let i = 0; i < 40; i++) {

    await sleep(500);

    const r = await call(
      "Runtime.evaluate",
      {
        expression: `
          (() => {
            const v = document.querySelector("video");

            if (!v) return false;

            return v.readyState >= 2;
          })()
        `,
        returnByValue: true
      }
    );

    if (r.result.value === true) {
      videoReady = true;
      break;
    }
  }

  if (!videoReady) {
    throw new Error("SM3_VIDEO_NOT_READY");
  }

  console.log("VIDEO_READY=true");


  // --------------------------------------------------------
  // FORCAR REPRODUCAO NORMAL
  // --------------------------------------------------------

  const playResult = await call(
    "Runtime.evaluate",
    {
      expression: `
        (async () => {
          const v = document.querySelector("video");

          if (!v) return "NO_VIDEO";

          v.muted = true;

          try {
            v.currentTime = 0;
          } catch {}

          try {
            await v.play();
            return "PLAYING";
          }
          catch (e) {
            return "PLAY_FAILED:" + String(e);
          }
        })()
      `,
      awaitPromise: true,
      returnByValue: true
    }
  );

  console.log(
    "PLAY_RESULT=" +
    playResult.result.value
  );


  // --------------------------------------------------------
  // AGUARDAR PRIMEIRO FRAGMENTO
  // --------------------------------------------------------

  for (let i = 0; i < 30; i++) {

    if (candidates.length > 0) {
      break;
    }

    await sleep(500);
  }

  if (!candidates.length) {
    throw new Error(
      "SM3_NO_MEDIA_FRAGMENT_AFTER_PLAY"
    );
  }

  console.log(
    "CAPTURED_FRAGMENTS=" +
    candidates.length
  );


  // --------------------------------------------------------
  // ESCOLHER MENOR FRAGMENTO
  // --------------------------------------------------------

  candidates.sort(
    (a, b) =>
      a.expectedBytes -
      b.expectedBytes
  );

  const target = candidates[0];

  const pathHash = crypto
    .createHash("sha256")
    .update(target.path)
    .digest("hex")
    .slice(0, 12);

  console.log(
    "TARGET_HOST=" +
    target.host
  );

  console.log(
    "TARGET_PATH_HASH=" +
    pathHash
  );

  console.log(
    "BYTESTART=" +
    target.start
  );

  console.log(
    "BYTEEND=" +
    target.end
  );

  console.log(
    "EXPECTED_BYTES=" +
    target.expectedBytes
  );


  // --------------------------------------------------------
  // REFETCH SOMENTE EM MEMORIA
  // --------------------------------------------------------

  const response = await fetch(
    target.url,
    {
      redirect: "follow"
    }
  );

  const contentType =
    response.headers.get(
      "content-type"
    ) || "";

  const buffer = Buffer.from(
    await response.arrayBuffer()
  );

  const sha = crypto
    .createHash("sha256")
    .update(buffer)
    .digest("hex");

  console.log("");
  console.log(
    "REFETCH_STATUS=" +
    response.status
  );

  console.log(
    "REFETCH_CONTENT_TYPE=" +
    contentType
  );

  console.log(
    "RECEIVED_BYTES=" +
    buffer.length
  );

  console.log(
    "FRAGMENT_SHA256=" +
    sha
  );

  ws.close();


  // --------------------------------------------------------
  // ASSERT
  // --------------------------------------------------------

  if (
    response.ok &&
    contentType
      .toLowerCase()
      .includes("video/mp4") &&
    buffer.length ===
      target.expectedBytes
  ) {

    console.log("");
    console.log(
      "SM3_09C3_G3A_MEMORY_FRAGMENT_REFETCH_PASS"
    );

  }
  else {

    console.log("");
    console.log(
      "SM3_09C3_G3A_MEMORY_FRAGMENT_REFETCH_FAIL"
    );
  }
}

main().catch(err => {
  console.error(
    err?.stack || String(err)
  );

  process.exit(1);
});
