import assert from "node:assert/strict";
import { createHash, randomUUID } from "node:crypto";
import { mkdir, readFile, rename, rm, symlink, writeFile } from "node:fs/promises";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { setTimeout as delay } from "node:timers/promises";
import test from "node:test";
import {
  CANVAS_ID, ChartError, INPUT_SCHEMA, MAX_HTML_BYTES, createChartCanvasOptions,
  createViewer, readArtifact, validateHtml, validateLocalPath,
} from "./viewer.mjs";

const directory = path.dirname(fileURLToPath(import.meta.url));
const script = "document.documentElement.dataset.chart = 'ready';";
const hash = createHash("sha256").update(script).digest("base64");
const csp = `default-src 'none'; script-src 'sha256-${hash}'; style-src 'unsafe-inline'; `
  + "img-src data: blob:; connect-src 'none'; base-uri 'none'; form-action 'none'; object-src 'none'";
function html(payload = { format: "sqlmem-chart", version: 1 }) {
  return Buffer.from(`<!doctype html><html><head><meta http-equiv="Content-Security-Policy" content="${csp}">`
    + `</head><body><script id="sqlmem-chart-data" type="application/json">${JSON.stringify(payload)}</script>`
    + `<script>${script}</script></body></html>`);
}

async function fixture(t) {
  // Keep all test artifacts inside the owned extension, never in an OS temporary directory.
  const base = path.join(directory, `.test-artifacts-${randomUUID()}`);
  const outputRoot = path.join(base, "any-workspace", "build", "charts");
  const chartId = randomUUID().replaceAll("-", "");
  const file = path.join(outputRoot, "nested", `${chartId}.html`);
  await mkdir(path.dirname(file), { recursive: true });
  await writeFile(file, html());
  t.after(() => rm(base, { recursive: true, force: true }));
  return { base, chartId, input: { path: file, outputRoot } };
}

async function viewerFixture(t, options) {
  const f = await fixture(t);
  const viewer = await createViewer(f.input, options);
  t.after(() => viewer.close());
  return { ...f, viewer };
}

function request(url, { method = "GET", headers = {}, route } = {}) {
  const target = new URL(url);
  return new Promise((resolve, reject) => {
    const req = http.request({
      hostname: target.hostname, port: target.port, path: route ?? target.pathname, method, headers,
    }, (response) => {
      const chunks = [];
      response.on("data", (chunk) => chunks.push(chunk));
      response.on("end", () => resolve({
        status: response.statusCode, headers: response.headers, body: Buffer.concat(chunks),
      }));
    });
    req.on("error", reject);
    req.end();
  });
}

function rawRequest(url, value) {
  const target = new URL(url);
  return new Promise((resolve, reject) => {
    const socket = net.createConnection({ host: target.hostname, port: Number(target.port) });
    let response = "";
    socket.setEncoding("utf8");
    socket.setTimeout(3000, () => socket.destroy(new Error("raw request timed out")));
    socket.on("connect", () => socket.end(value));
    socket.on("data", (chunk) => { response += chunk; });
    socket.on("end", () => resolve(response));
    socket.on("error", reject);
  });
}

test("artifact policy accepts exact bytes from any local workspace build/charts root", async (t) => {
  const f = await fixture(t);
  const result = await readArtifact(f.input);
  assert.equal(result.chart_id, f.chartId);
  assert.equal(result.path, f.input.path);
  assert.deepEqual(result.body, html());
});

test("artifact policy rejects relative paths, traversal, extra fields, invalid IDs and wrong roots", async (t) => {
  const f = await fixture(t);
  const bad = [
    { ...f.input, path: path.relative(directory, f.input.path) },
    { ...f.input, path: path.join(path.dirname(f.input.path), "..", "nested", `${f.chartId}.html`) + path.sep + ".." },
    { ...f.input, sql: "SELECT 1" },
    { path: f.input.path },
    { ...f.input, outputRoot: path.dirname(f.input.outputRoot) },
    { ...f.input, path: `${f.input.path}\0` },
  ];
  for (const input of bad) await assert.rejects(readArtifact(input), ChartError);
  for (const name of ["bad.html", `${f.chartId}.HTML`, `${f.chartId}.svg`, "a".repeat(33) + ".html"]) {
    const file = path.join(f.input.outputRoot, name);
    await writeFile(file, html());
    await assert.rejects(readArtifact({ ...f.input, path: file }), { code: "unsafe_path" });
  }
  const outside = path.join(f.base, `${f.chartId}.html`);
  await writeFile(outside, html());
  await assert.rejects(readArtifact({ ...f.input, path: outside }), { code: "unsafe_path" });
});

test("Windows network and device spellings fail lexically before filesystem access", {
  skip: process.platform !== "win32",
}, async () => {
  for (const outputRoot of [
    "//untrusted.invalid/share/build/charts",
    "//?/C:/build/charts",
    "/\\untrusted.invalid/share/build/charts",
    "\\/untrusted.invalid\\share\\build\\charts",
    "\\\\untrusted.invalid\\share\\build\\charts",
    "C:/build/charts:alternate-stream",
  ]) {
    assert.throws(() => validateLocalPath(outputRoot), { code: "invalid_path" });
  }
});

test("artifact policy rejects a root or artifact ancestor junction without following it", async (t) => {
  const f = await fixture(t);
  const alias = path.join(f.base, "alias");
  await symlink(path.dirname(f.input.outputRoot), alias, process.platform === "win32" ? "junction" : "dir");
  await assert.rejects(readArtifact({
    outputRoot: path.join(alias, "charts"),
    path: path.join(alias, "charts", "nested", `${f.chartId}.html`),
  }), { code: "unsafe_path" });
  const aliasWithin = path.join(f.input.outputRoot, "redirect");
  await symlink(path.dirname(f.input.path), aliasWithin, process.platform === "win32" ? "junction" : "dir");
  await assert.rejects(readArtifact({
    ...f.input, path: path.join(aliasWithin, `${f.chartId}.html`),
  }), { code: "unsafe_path" });
});

test("artifact policy rejects directories, missing artifacts and oversize HTML", async (t) => {
  const f = await fixture(t);
  await writeFile(f.input.path, Buffer.alloc(MAX_HTML_BYTES + 1));
  await assert.rejects(readArtifact(f.input), { code: "chart_too_large" });
  await rm(f.input.path);
  await assert.rejects(readArtifact(f.input), { code: "chart_unavailable" });
  await mkdir(f.input.path);
  await assert.rejects(readArtifact(f.input), { code: "unsafe_path" });
});

test("HTML policy validates format/version, UTF-8, CSP and executable inline hashes", () => {
  assert.doesNotThrow(() => validateHtml(html()));
  const invalid = [
    html({ format: "other", version: 1 }), html({ format: "sqlmem-chart", version: 2 }),
    Buffer.from("<html>not generated</html>"), Buffer.from([255]), Buffer.alloc(MAX_HTML_BYTES + 1),
    Buffer.from(html().toString().replace("Content-Security-Policy", "Other-Policy")),
    Buffer.from(html().toString().replace("default-src 'none'", "default-src https:")),
    Buffer.from(html().toString().replace("base-uri 'none'", "base-uri https:")),
    Buffer.from(html().toString().replace(`'sha256-${hash}'`, "'unsafe-inline'")),
    Buffer.from(html().toString().replace("connect-src 'none'", "connect-src https:")),
    Buffer.from(html().toString().replace("object-src 'none'", "script-src-elem 'unsafe-inline'")),
    Buffer.from(html().toString().replace(`<script>${script}`, `<script src="https://invalid.example/a.js">${script}`)),
    Buffer.from(html().toString().replace(script, "arbitraryCode();")),
    Buffer.from(html().toString().replace('id="sqlmem-chart-data"', 'id="other"')),
    Buffer.from(html().toString().replace("</head>", `<script>${script}</script></head>`).replace("<head>", `<head><script>${script}</script>`)),
  ];
  for (const bytes of invalid) assert.throws(() => validateHtml(bytes), ChartError);
});

test("HTTP serves exact inline HTML, HEAD and attachment with private-data-safe headers", async (t) => {
  const { viewer, input, chartId } = await viewerFixture(t);
  assert.match(viewer.url, /^http:\/\/127\.0\.0\.1:\d+\/$/);
  assert.ok(!viewer.url.includes(chartId));
  assert.ok(!viewer.url.includes(encodeURIComponent(input.path)));
  const response = await request(viewer.url);
  assert.equal(response.status, 200);
  assert.deepEqual(response.body, await readFile(input.path));
  assert.equal(response.headers["cache-control"], "no-store");
  assert.equal(response.headers["referrer-policy"], "no-referrer");
  assert.equal(response.headers["x-content-type-options"], "nosniff");
  assert.equal(response.headers["access-control-allow-origin"], undefined);
  // Repeat the renderer's exact validated restrictions, never a conflicting script policy.
  assert.equal(response.headers["content-security-policy"], csp);
  const head = await request(viewer.url, { method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(head.body.length, 0);
  assert.equal(Number(head.headers["content-length"]), html().length);
  const download = await request(viewer.url, { route: "/download" });
  assert.equal(download.status, 200);
  assert.deepEqual(download.body, html());
  assert.equal(download.headers["content-disposition"], `attachment; filename="${chartId}.html"`);
});

test("HTTP rejects all write methods, foreign hosts/origins, query strings and encoded/arbitrary routes", async (t) => {
  const { viewer } = await viewerFixture(t);
  for (const method of ["POST", "PUT", "DELETE", "PATCH", "OPTIONS"]) {
    assert.equal((await request(viewer.url, { method })).status, 405);
  }
  for (const route of ["/?x=1", "/download?x=1", "/%2f", "/%2e%2e/", "/../", "/download/", "//", "/anything"]) {
    assert.equal((await request(viewer.url, { route })).status, 404);
  }
  for (const host of ["localhost", "attacker.example", "127.0.0.1", `${new URL(viewer.url).host}.evil`]) {
    assert.equal((await request(viewer.url, { headers: { Host: host } })).status, 403);
  }
  for (const origin of ["null", "https://attacker.example", `${viewer.url}extra`]) {
    assert.equal((await request(viewer.url, { headers: { Origin: origin } })).status, 403);
  }
  assert.equal((await request(viewer.url, { headers: { Origin: new URL(viewer.url).origin } })).status, 200);
  assert.equal((await request(viewer.url, { headers: { "Content-Length": "1" } })).status, 400);
});

test("HTTP rejects malformed or oversized headers, duplicate hosts and duplicate origins", async (t) => {
  const { viewer } = await viewerFixture(t);
  const host = new URL(viewer.url).host;
  for (const raw of [
    "INVALID REQUEST\r\n\r\n",
    `GET / HTTP/1.1\r\nHost: ${host}\r\nX: ${"x".repeat(17000)}\r\n\r\n`,
    `GET / HTTP/1.1\r\nHost: ${host}\r\nHost: ${host}\r\n\r\n`,
    `GET / HTTP/1.1\r\nHost: ${host}\r\nOrigin: http://${host}\r\nOrigin: http://${host}\r\n\r\n`,
  ]) {
    const response = await rawRequest(viewer.url, raw);
    assert.ok(!response.startsWith("HTTP/1.1 200"), "Malformed requests must not serve chart data.");
    assert.ok(!response.includes("sqlmem-chart-data"));
  }
});

test("every HTTP read revalidates the artifact, including HEAD and download", async (t) => {
  const { viewer, input } = await viewerFixture(t);
  await writeFile(input.path, "<html>replaced</html>");
  for (const options of [{}, { method: "HEAD" }, { route: "/download" }]) {
    const response = await request(viewer.url, options);
    assert.equal(response.status, 410);
    assert.ok(!response.body.toString().includes(input.path));
  }
  await writeFile(input.path, html());
  assert.equal((await request(viewer.url)).status, 200);
  const moved = path.join(path.dirname(input.path), "original");
  await rename(input.path, moved);
  await symlink(moved, input.path, process.platform === "win32" ? "file" : undefined).catch(async (error) => {
    if (error.code !== "EPERM") throw error;
    await mkdir(input.path);
  });
  assert.equal((await request(viewer.url)).status, 410);
});

test("viewer caps active requests at eight and closes open sockets", async (t) => {
  const f = await fixture(t);
  const artifact = await readArtifact(f.input);
  let release;
  const gate = new Promise((resolve) => { release = resolve; });
  let calls = 0;
  const viewer = await createViewer(f.input, { read: async () => {
    calls += 1;
    if (calls > 1) await gate;
    return artifact;
  } });
  t.after(() => viewer.close());
  const pending = Array.from({ length: 8 }, () => request(viewer.url));
  for (let i = 0; i < 100 && calls < 9; i += 1) await delay(5);
  assert.equal(calls, 9);
  assert.equal((await request(viewer.url)).status, 503);
  release();
  assert.ok((await Promise.all(pending)).every((result) => result.status === 200));
  const target = new URL(viewer.url);
  const socket = net.createConnection({ host: target.hostname, port: Number(target.port) });
  await new Promise((resolve) => socket.once("connect", resolve));
  const disconnected = new Promise((resolve) => socket.once("close", resolve));
  await viewer.close();
  await disconnected;
  assert.equal(viewer.closed, true);
  await viewer.close();
});

test("idle and absolute lifetime expire without hidden-view close callbacks", async (t) => {
  for (const options of [{ idleMs: 30, lifetimeMs: 1000 }, { idleMs: 1000, lifetimeMs: 30 }]) {
    const { viewer } = await viewerFixture(t, options);
    await delay(70);
    assert.equal(viewer.closed, true);
    await assert.rejects(viewer.refresh(), { code: "viewer_closed" });
    await assert.rejects(request(viewer.url), /ECONNREFUSED|ECONNRESET|socket hang up/);
  }
});

class MockCanvasError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

test("SDK options expose exact strict schemas, action handlers and raw descriptor shapes", async (t) => {
  const f = await fixture(t);
  const options = createChartCanvasOptions(MockCanvasError);
  const context = { sessionId: "session", instanceId: "instance", input: f.input };
  t.after(() => options.onClose(context));
  assert.equal(options.id, CANVAS_ID);
  assert.equal(options.inputSchema, INPUT_SCHEMA);
  assert.deepEqual(INPUT_SCHEMA.required, ["path", "outputRoot"]);
  assert.equal(INPUT_SCHEMA.additionalProperties, false);
  assert.deepEqual(options.actions.map((action) => action.name), ["refresh", "show_chart", "download_html"]);
  const opened = await options.open(context);
  for (const action of options.actions) {
    assert.equal(action.inputSchema.additionalProperties, false);
    const result = await action.handler({
      ...context, actionName: action.name, input: action.name === "show_chart" ? { chart_id: f.chartId } : {},
    });
    assert.deepEqual(Object.keys(result).sort(), ["chart_id", "path", "url"]);
    assert.equal(result.chart_id, f.chartId);
    assert.equal(result.path, f.input.path);
    assert.equal(result.url, action.name === "download_html" ? `${opened.url}download` : opened.url);
  }
});

test("actions enforce current chart membership, exact envelopes and registered lifecycle", async (t) => {
  const f = await fixture(t);
  const options = createChartCanvasOptions(MockCanvasError);
  const context = { sessionId: "session", instanceId: "instance", input: f.input };
  t.after(() => options.onClose(context));
  const refresh = options.actions.find((action) => action.name === "refresh");
  const show = options.actions.find((action) => action.name === "show_chart");
  await assert.rejects(refresh.handler({ ...context, actionName: "refresh", input: {} }), { code: "viewer_closed" });
  await options.open(context);
  for (const input of [undefined, null, [], { path: f.input.path }]) {
    await assert.rejects(refresh.handler({ ...context, actionName: "refresh", input }), { code: "invalid_input" });
  }
  await assert.rejects(refresh.handler({ ...context, actionName: "unknown", input: {} }), { code: "invalid_action" });
  for (const input of [{ chart_id: "a".repeat(32) }, { chart_id: "../../private" }, { chart_id: f.chartId, path: f.input.path }]) {
    await assert.rejects(show.handler({ ...context, actionName: "show_chart", input }), MockCanvasError);
  }
  await options.onClose(context);
  await assert.rejects(show.handler({ ...context, actionName: "show_chart", input: { chart_id: f.chartId } }), { code: "viewer_closed" });
});

test("idempotent and concurrent reopen preserves URL; replacement and close destroy old servers", async (t) => {
  const f = await fixture(t);
  const other = await fixture(t);
  const options = createChartCanvasOptions(MockCanvasError);
  const context = { sessionId: "s", instanceId: "stable-instance", input: f.input };
  t.after(() => options.onClose(context));
  const opened = await options.open(context);
  const reopened = await Promise.all([options.open(context), options.open(context)]);
  assert.ok(reopened.every((result) => result.url === opened.url));
  const replacement = await options.open({ ...context, input: other.input });
  assert.notEqual(replacement.url, opened.url);
  await assert.rejects(request(opened.url), /ECONNREFUSED|ECONNRESET|socket hang up/);
  assert.equal((await request(replacement.url)).status, 200);
  await assert.rejects(options.open({ ...context, input: { ...other.input, arbitrary: true } }), { code: "invalid_input" });
  assert.equal((await request(replacement.url)).status, 200);
  await options.onClose(context);
  await assert.rejects(request(replacement.url), /ECONNREFUSED|ECONNRESET|socket hang up/);
  // New process/state identity requires only the stable artifact input.
  const fresh = createChartCanvasOptions(MockCanvasError);
  const restored = await fresh.open(context);
  assert.deepEqual((await request(restored.url)).body, html());
  await fresh.onClose(context);
});

test("registry reserves concurrent opens and bounds live viewers", async (t) => {
  const f = await fixture(t);
  const options = createChartCanvasOptions(MockCanvasError);
  const contexts = Array.from({ length: 20 }, (_, i) => ({
    sessionId: "s", instanceId: `instance-${i}`, input: f.input,
  }));
  t.after(() => Promise.all(contexts.map((ctx) => options.onClose(ctx))));
  const outcomes = await Promise.allSettled(contexts.map((ctx) => options.open(ctx)));
  assert.equal(outcomes.filter((result) => result.status === "fulfilled").length, 16);
  for (const result of outcomes.filter((entry) => entry.status === "rejected")) {
    assert.equal(result.reason.code, "viewer_limit");
  }
});
