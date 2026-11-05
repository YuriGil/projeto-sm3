const CDP = "http://127.0.0.1:9222";
const WORKER = "http://127.0.0.1:8090";
const PROFILE_ID = "RP_0a468e360f9ae70383b235f10e445233";

async function main() {

  // ----------------------------------------------------------
  // 1. LOCALIZAR ABA DO PERFIL
  // ----------------------------------------------------------

  const targets = await fetch(CDP + "/json/list").then(r => r.json());

  const page = targets.find(
    t =>
      t.type === "page" &&
      typeof t.url === "string" &&
      t.url.includes("instagram.com/fredao_oliveira")
  );

  if (!page) {
    throw new Error("SM3_INSTAGRAM_PROFILE_TAB_NOT_FOUND");
  }

  // ----------------------------------------------------------
  // 2. CONECTAR AO CDP
  // ----------------------------------------------------------

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

  // ----------------------------------------------------------
  // 3. EXTRAIR REELS VISÍVEIS
  // ----------------------------------------------------------

  const result = await call("Runtime.evaluate", {
    expression: `
      JSON.stringify(
        [...document.querySelectorAll('a[href]')]
          .map(a => a.href)
          .filter(h => h.includes('/reel/'))
          .filter((v, i, a) => a.indexOf(v) === i)
      )
    `,
    returnByValue: true
  });

  ws.close();

  const rawLinks = JSON.parse(result.result.value || "[]");

  // ----------------------------------------------------------
  // 4. CANONICALIZAR
  //
  // Entrada possível:
  // /fredao_oliveira/reel/ABC123/
  //
  // Saída:
  // /reel/ABC123/
  // ----------------------------------------------------------

  const reels = [];

  for (const rawUrl of rawLinks) {

    const u = new URL(rawUrl);

    const match = u.pathname.match(
      /\/(?:[^/]+\/)?reel\/([^/?#]+)\/?/i
    );

    if (!match) continue;

    const shortcode = match[1];

    reels.push({
      content_type: "REEL",
      platform_item_id: shortcode,
      url: `https://www.instagram.com/reel/${shortcode}/`,
      raw: {
        discovered_href: rawUrl,
        discovery_mode: "BROWSER_SESSION_DOM"
      }
    });
  }

  const unique = [
    ...new Map(
      reels.map(x => [x.platform_item_id, x])
    ).values()
  ];

  console.log("RAW_REEL_LINKS=" + rawLinks.length);
  console.log("CANONICAL_REELS=" + unique.length);

  unique.forEach((x, i) => {
    console.log(
      String(i + 1).padStart(2, "0") +
      " " +
      x.platform_item_id +
      " " +
      x.url
    );
  });

  if (!unique.length) {
    throw new Error("SM3_NO_CANONICAL_REELS");
  }

  // ----------------------------------------------------------
  // 5. ENVIAR AO WORKER EM DRY RUN
  // ----------------------------------------------------------

  const payload = {
    reference_profile_id: PROFILE_ID,
    provider: "BROWSER_SESSION",
    items: unique,
    create_reference_items: true,
    dry_run: true,
    notes: "SM3_09C3_F7_REAL_BROWSER_DRY_RUN"
  };

  const response = await fetch(
    WORKER + "/production/reference-corpus/content-discovery/ingest",
    {
      method: "POST",
      headers: {
        "content-type": "application/json"
      },
      body: JSON.stringify(payload)
    }
  );

  const body = await response.json();

  console.log("");
  console.log("WORKER_HTTP=" + response.status);
  console.log("WORKER_OK=" + body.ok);
  console.log("CONTRACT=" + body.contract_version);
  console.log("PROVIDER=" + body.provider);
  console.log("DRY_RUN=" + body.dry_run);
  console.log("WORKER_COUNT=" + body.count);
  console.log("SKIPPED_DUPLICATES=" + body.skipped_duplicates);

  if (!response.ok) {
    console.log(JSON.stringify(body, null, 2));
    throw new Error("SM3_WORKER_DISCOVERY_REQUEST_FAILED");
  }

  const returned = body.results || [];

  returned.forEach((x, i) => {
    console.log(
      "RESULT_" +
      String(i + 1).padStart(2, "0") +
      "=" +
      x.content_type +
      "|" +
      x.platform_item_id +
      "|" +
      x.canonical_url
    );
  });

  // ----------------------------------------------------------
  // 6. ASSERT
  // ----------------------------------------------------------

  if (
    body.ok === true &&
    body.contract_version === "SM3_REFERENCE_CONTENT_DISCOVERY_V1" &&
    body.provider === "BROWSER_SESSION" &&
    body.dry_run === true &&
    body.count === unique.length &&
    returned.length === unique.length
  ) {
    console.log("");
    console.log("SM3_09C3_F7_BROWSER_TO_WORKER_DRY_RUN_PASS");
  } else {
    throw new Error("SM3_09C3_F7_ASSERT_FAILED");
  }
}

main().catch(err => {
  console.error(err?.stack || String(err));
  process.exit(1);
});
