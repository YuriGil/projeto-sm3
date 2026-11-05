const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");

const CDP = "http://127.0.0.1:9222";
const OUT = "D:\\MOLOTOV_SOCIAL_OS_RC7\\runtime\\reference_acquire\\g3b";

const sleep = ms => new Promise(r => setTimeout(r, ms));

function sha256(data) {
  return crypto
    .createHash("sha256")
    .update(data)
    .digest("hex");
}

function pathHash(p) {
  return sha256(p).slice(0, 12);
}

async function main() {

  fs.mkdirSync(OUT, { recursive: true });

  for (const name of fs.readdirSync(OUT)) {
    if (
      name.startsWith("SM3_G3B_TRACK_") ||
      name === "manifest.json"
    ) {
      fs.rmSync(path.join(OUT, name), {
        force: true
      });
    }
  }

  const targets = await fetch(
    CDP + "/json/list"
  ).then(r => r.json());

  const page = targets.find(
    t =>
      t.type === "page" &&
      typeof t.url === "string" &&
      t.url.includes("/reel/DdW4KBZhpEd")
  );

  if (!page) {
    throw new Error("SM3_REEL_TAB_NOT_FOUND");
  }

  const ws = new WebSocket(
    page.webSocketDebuggerUrl
  );

  let id = 0;

  const pending = new Map();
  const fragments = [];

  ws.onmessage = e => {

    const m = JSON.parse(e.data);

    if (
      m.id &&
      pending.has(m.id)
    ) {

      const p = pending.get(m.id);
      pending.delete(m.id);

      if (m.error) {
        p.reject(m.error);
      }

      if (!m.error) {
        p.resolve(m.result);
      }

      return;
    }

    if (
      m.method !==
      "Network.responseReceived"
    ) {
      return;
    }

    const r =
      m.params.response || {};

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

      fragments.push({
        url: r.url,
        host: u.host,
        resourcePath: u.pathname,
        start,
        end,
        expectedBytes:
          end - start + 1
      });

    } catch {}
  };

  await new Promise(
    (resolve, reject) => {

      ws.onopen = resolve;
      ws.onerror = reject;

    }
  );

  function call(
    method,
    params = {}
  ) {

    return new Promise(
      (resolve, reject) => {

        const n = ++id;

        pending.set(n, {
          resolve,
          reject
        });

        ws.send(
          JSON.stringify({
            id: n,
            method,
            params
          })
        );
      }
    );
  }

  await call("Network.enable");
  await call("Page.enable");
  await call("Runtime.enable");

  console.log(
    "G3B_CAPTURE_START=true"
  );

  await call(
    "Page.reload",
    {
      ignoreCache: true
    }
  );


  // ------------------------------------------------------
  // AGUARDAR VIDEO
  // ------------------------------------------------------

  let duration = null;

  for (
    let i = 0;
    i < 40;
    i++
  ) {

    await sleep(500);

    const r = await call(
      "Runtime.evaluate",
      {
        expression: `
          (() => {
            const v =
              document.querySelector("video");

            if (!v) return null;

            return {
              readyState:
                v.readyState,

              duration:
                Number.isFinite(v.duration)
                  ? v.duration
                  : null
            };
          })()
        `,
        returnByValue: true
      }
    );

    const state =
      r.result.value;

    if (
      state &&
      state.readyState >= 2 &&
      state.duration
    ) {

      duration =
        state.duration;

      break;
    }
  }

  if (!duration) {
    throw new Error(
      "SM3_VIDEO_NOT_READY"
    );
  }

  console.log(
    "DURATION=" + duration
  );


  // ------------------------------------------------------
  // REPRODUZIR E CAPTURAR
  // ------------------------------------------------------

  const play = await call(
    "Runtime.evaluate",
    {
      expression: `
        (async () => {

          const v =
            document.querySelector("video");

          if (!v) {
            return "NO_VIDEO";
          }

          v.muted = true;

          try {
            v.currentTime = 0;
          } catch {}

          try {
            await v.play();
            return "PLAYING";
          }
          catch (e) {
            return (
              "PLAY_FAILED:" +
              String(e)
            );
          }

        })()
      `,
      awaitPromise: true,
      returnByValue: true
    }
  );

  console.log(
    "PLAY_RESULT=" +
    play.result.value
  );


  // ------------------------------------------------------
  // OBSERVAR A REPRODUCAO
  // ------------------------------------------------------

  for (
    let i = 0;
    i < 36;
    i++
  ) {

    await sleep(750);

    const r = await call(
      "Runtime.evaluate",
      {
        expression: `
          (() => {

            const v =
              document.querySelector("video");

            if (!v) return null;

            if (
              v.paused &&
              v.currentTime <
                v.duration - 0.25
            ) {
              v.play().catch(() => {});
            }

            return {
              currentTime:
                v.currentTime,

              duration:
                v.duration,

              paused:
                v.paused
            };

          })()
        `,
        returnByValue: true
      }
    );

    const s =
      r.result.value;

    if (
      s &&
      s.duration &&
      s.currentTime >=
        s.duration - 0.25
    ) {
      break;
    }
  }

  await sleep(1500);

  ws.close();

  console.log(
    "RAW_FRAGMENT_EVENTS=" +
    fragments.length
  );

  if (!fragments.length) {
    throw new Error(
      "SM3_G3B_NO_FRAGMENTS"
    );
  }


  // ------------------------------------------------------
  // AGRUPAR POR RECURSO
  // ------------------------------------------------------

  const groups =
    new Map();

  for (const f of fragments) {

    const key =
      f.host +
      "|" +
      f.resourcePath;

    if (!groups.has(key)) {

      groups.set(key, {
        host: f.host,
        resourcePath:
          f.resourcePath,
        fragments: []
      });

    }

    groups
      .get(key)
      .fragments
      .push(f);
  }


  // ------------------------------------------------------
  // ANALISAR COBERTURA
  // ------------------------------------------------------

  const usable = [];

  for (
    const group
    of groups.values()
  ) {

    const unique = [
      ...new Map(
        group.fragments.map(
          f => [
            `${f.start}-${f.end}`,
            f
          ]
        )
      ).values()
    ].sort(
      (a, b) =>
        a.start - b.start
    );

    const merged = [];

    for (const f of unique) {

      if (!merged.length) {

        merged.push([
          f.start,
          f.end
        ]);

        continue;
      }

      const last =
        merged[
          merged.length - 1
        ];

      if (
        f.start <=
        last[1] + 1
      ) {

        last[1] =
          Math.max(
            last[1],
            f.end
          );

      }

      if (
        f.start >
        last[1] + 1
      ) {

        merged.push([
          f.start,
          f.end
        ]);

      }
    }

    const covered =
      merged.reduce(
        (sum, r) =>
          sum +
          (
            r[1] -
            r[0] +
            1
          ),
        0
      );

    const continuous =
      merged.length === 1 &&
      merged[0][0] === 0;

    console.log(
      "RESOURCE=" +
      pathHash(
        group.resourcePath
      ) +
      "|FRAGMENTS=" +
      unique.length +
      "|RANGES=" +
      merged.length +
      "|START=" +
      (
        merged[0]?.[0] ??
        "null"
      ) +
      "|END=" +
      (
        merged.at(-1)?.[1] ??
        "null"
      ) +
      "|BYTES=" +
      covered +
      "|CONTINUOUS=" +
      continuous
    );

    if (
      continuous &&
      covered > 10000
    ) {

      usable.push({
        ...group,
        fragments:
          unique,
        totalBytes:
          merged[0][1] + 1
      });

    }
  }

  usable.sort(
    (a, b) =>
      b.totalBytes -
      a.totalBytes
  );

  console.log(
    "USABLE_TRACKS=" +
    usable.length
  );

  if (!usable.length) {
    throw new Error(
      "SM3_G3B_NO_CONTINUOUS_TRACK"
    );
  }


  // ------------------------------------------------------
  // RECONSTRUIR CADA TRACK
  // ------------------------------------------------------

  const manifest = [];

  let trackNumber = 0;

  for (const track of usable) {

    trackNumber++;

    const buffer =
      Buffer.alloc(
        track.totalBytes
      );

    let verifiedFragments = 0;

    for (
      const fragment
      of track.fragments
    ) {

      const response =
        await fetch(
          fragment.url,
          {
            redirect: "follow"
          }
        );

      if (!response.ok) {
        throw new Error(
          "SM3_G3B_FRAGMENT_HTTP_" +
          response.status
        );
      }

      const data =
        Buffer.from(
          await response.arrayBuffer()
        );

      if (
        data.length !==
        fragment.expectedBytes
      ) {

        throw new Error(
          "SM3_G3B_FRAGMENT_SIZE_MISMATCH_" +
          fragment.start +
          "_" +
          fragment.end +
          "_EXPECTED_" +
          fragment.expectedBytes +
          "_GOT_" +
          data.length
        );
      }

      data.copy(
        buffer,
        fragment.start
      );

      verifiedFragments++;
    }

    const filename =
      "SM3_G3B_TRACK_" +
      String(trackNumber)
        .padStart(2, "0") +
      ".mp4";

    const filePath =
      path.join(
        OUT,
        filename
      );

    fs.writeFileSync(
      filePath,
      buffer
    );

    const fileSha =
      sha256(buffer);

    const stat =
      fs.statSync(
        filePath
      );

    if (
      stat.size !==
      track.totalBytes
    ) {
      throw new Error(
        "SM3_G3B_FINAL_SIZE_MISMATCH"
      );
    }

    manifest.push({
      track:
        trackNumber,

      file:
        filePath,

      pathHash:
        pathHash(
          track.resourcePath
        ),

      bytes:
        stat.size,

      sha256:
        fileSha,

      fragments:
        track.fragments.length,

      verifiedFragments,

      continuousFromZero:
        true,

      signedUrlsPersisted:
        false
    });

    console.log(
      "TRACK_" +
      String(trackNumber)
        .padStart(2, "0") +
      "_RECONSTRUCTED=" +
      stat.size +
      "|SHA256=" +
      fileSha
    );
  }


  // ------------------------------------------------------
  // MANIFESTO SEM URLS
  // ------------------------------------------------------

  const manifestPath =
    path.join(
      OUT,
      "manifest.json"
    );

  fs.writeFileSync(
    manifestPath,
    JSON.stringify(
      {
        contract:
          "SM3_G3B_TEMP_TRACK_RECONSTRUCTION_V1",

        reel:
          "DdW4KBZhpEd",

        trackCount:
          manifest.length,

        signedUrlsPersisted:
          false,

        tracks:
          manifest
      },
      null,
      2
    )
  );

  console.log(
    "MANIFEST=" +
    manifestPath
  );

  console.log(
    "SM3_09C3_G3B_RECONSTRUCTION_PASS"
  );
}

main().catch(err => {

  console.error(
    err?.stack ||
    String(err)
  );

  process.exit(1);

});
