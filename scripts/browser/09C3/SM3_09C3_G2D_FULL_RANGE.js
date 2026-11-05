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

  if (!page) throw new Error("SM3_REEL_TAB_NOT_FOUND");

  const ws = new WebSocket(page.webSocketDebuggerUrl);

  let id = 0;
  const pending = new Map();
  const fragments = [];

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

      const start = Number(u.searchParams.get("bytestart"));
      const end   = Number(u.searchParams.get("byteend"));

      if (!Number.isFinite(start) || !Number.isFinite(end)) return;

      fragments.push({
        host: u.host,
        path: u.pathname,
        start,
        end
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

      ws.send(JSON.stringify({ id: n, method, params }));
    });
  }

  await call("Network.enable");
  await call("Page.enable");
  await call("Runtime.enable");

  console.log("RELOADING_REEL=true");

  await call("Page.reload", { ignoreCache: false });

  // Esperar o elemento de vídeo ficar disponível.
  let info = null;

  for (let i = 0; i < 40; i++) {
    await sleep(500);

    const r = await call("Runtime.evaluate", {
      expression: `
        (() => {
          const v = document.querySelector("video");
          if (!v) return null;

          return {
            duration: Number.isFinite(v.duration) ? v.duration : null,
            readyState: v.readyState
          };
        })()
      `,
      returnByValue: true
    });

    info = r.result.value;

    if (
      info &&
      info.duration &&
      info.readyState >= 2
    ) break;
  }

  if (!info || !info.duration) {
    throw new Error("SM3_VIDEO_NOT_READY");
  }

  console.log("DURATION=" + info.duration);

  // Reprodução normal, apenas silenciada.
  await call("Runtime.evaluate", {
    expression: `
      (() => {
        const v = document.querySelector("video");
        if (!v) return false;

        v.muted = true;
        v.currentTime = 0;
        v.play();

        return true;
      })()
    `,
    returnByValue: true
  });

  let ended = false;

  for (let i = 0; i < 50; i++) {
    await sleep(1000);

    const r = await call("Runtime.evaluate", {
      expression: `
        (() => {
          const v = document.querySelector("video");
          if (!v) return null;

          if (v.paused && !v.ended) {
            v.play().catch(() => {});
          }

          return {
            currentTime: v.currentTime,
            duration: v.duration,
            ended: v.ended
          };
        })()
      `,
      returnByValue: true
    });

    const state = r.result.value;

    if (state?.ended) {
      ended = true;
      break;
    }
  }

  await sleep(1500);
  ws.close();

  // Agrupar por recurso físico.
  const groups = new Map();

  for (const f of fragments) {
    const key = f.host + "|" + f.path;

    if (!groups.has(key)) {
      groups.set(key, {
        host: f.host,
        path: f.path,
        ranges: []
      });
    }

    groups.get(key).ranges.push([f.start, f.end]);
  }

  const results = [];

  for (const g of groups.values()) {
    const unique = [
      ...new Map(
        g.ranges.map(r => [`${r[0]}-${r[1]}`, r])
      ).values()
    ].sort((a, b) => a[0] - b[0]);

    const merged = [];

    for (const range of unique) {
      if (!merged.length) {
        merged.push([...range]);
        continue;
      }

      const last = merged[merged.length - 1];

      if (range[0] <= last[1] + 1) {
        last[1] = Math.max(last[1], range[1]);
      } else {
        merged.push([...range]);
      }
    }

    const coveredBytes = merged.reduce(
      (sum, r) => sum + (r[1] - r[0] + 1),
      0
    );

    const hash = crypto
      .createHash("sha256")
      .update(g.path)
      .digest("hex")
      .slice(0, 12);

    results.push({
      host: g.host,
      pathHash: hash,
      segments: unique.length,
      mergedRanges: merged.length,
      start: merged[0]?.[0] ?? null,
      end: merged.at(-1)?.[1] ?? null,
      coveredBytes,
      continuousFromZero:
        merged.length === 1 &&
        merged[0][0] === 0
    });
  }

  results.sort(
    (a, b) => b.coveredBytes - a.coveredBytes
  );

  console.log("");
  console.log("PLAYBACK_ENDED=" + ended);
  console.log("TRACK_COUNT=" + results.length);

  results.forEach((x, i) => {
    console.log(
      "TRACK_" + String(i + 1).padStart(2, "0") +
      " " + JSON.stringify(x)
    );
  });

  const continuous = results.filter(
    x => x.continuousFromZero && x.coveredBytes > 10000
  );

  console.log("");
  console.log("CONTINUOUS_ACTIVE_TRACKS=" + continuous.length);

  if (ended && continuous.length >= 1) {
    console.log("SM3_09C3_G2D_FULL_PLAYBACK_RANGE_PASS");
  } else {
    console.log("SM3_09C3_G2D_FULL_PLAYBACK_RANGE_INCOMPLETE");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
