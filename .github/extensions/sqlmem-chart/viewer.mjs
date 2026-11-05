import { createHash } from "node:crypto";
import { constants } from "node:fs";
import { lstat, open, realpath } from "node:fs/promises";
import http from "node:http";
import path from "node:path";

export const MAX_HTML_BYTES = 8 * 1024 * 1024;
export const CANVAS_ID = "sqlmem-chart";
const ID = /^[0-9a-f]{32}$/;
const EMPTY_SCHEMA = { type: "object", properties: {}, additionalProperties: false };
export const INPUT_SCHEMA = {
  type: "object",
  properties: {
    path: { type: "string", minLength: 1, maxLength: 32768 },
    outputRoot: { type: "string", minLength: 1, maxLength: 32768 },
  },
  required: ["path", "outputRoot"],
  additionalProperties: false,
};
const SHOW_SCHEMA = {
  type: "object",
  properties: { chart_id: { type: "string", pattern: "^[0-9a-f]{32}$" } },
  required: ["chart_id"],
  additionalProperties: false,
};

export class ChartError extends Error {
  constructor(code, message) {
    super(message);
    this.name = "ChartError";
    this.code = code;
  }
}

function fail(code, message) {
  throw new ChartError(code, message);
}

function exactObject(value, keys) {
  if (!value || typeof value !== "object" || Array.isArray(value)
    || Object.keys(value).length !== keys.length
    || !keys.every((key) => Object.hasOwn(value, key))) {
    fail("invalid_input", `Provide exactly ${keys.length ? keys.join(" and ") : "an empty object"}.`);
  }
}

export function validateLocalPath(value) {
  if (typeof value !== "string" || !value || value.length > 32768
    || value.includes("\0") || !path.isAbsolute(value)
    || value.split(/[\\/]/).some((part) => part === "." || part === "..")) {
    fail("invalid_path", "Provide an absolute, canonical generated HTML path and build/charts outputRoot.");
  }
  // Device namespaces and UNC shares are not local workspace artifacts.
  if (process.platform === "win32") {
    value = value.replaceAll("/", "\\");
    if (!/^[a-zA-Z]:\\/.test(value) || value.startsWith("\\\\") || value.slice(2).includes(":")) {
      fail("invalid_path", "Use a local drive path, not a device, stream, or network path.");
    }
  }
  return path.resolve(value);
}

const samePath = (a, b) => process.platform === "win32" ? a.toLowerCase() === b.toLowerCase() : a === b;

async function canonicalNoLinks(value) {
  const resolved = validateLocalPath(value);
  let current = path.parse(resolved).root;
  for (const part of resolved.slice(current.length).split(path.sep).filter(Boolean)) {
    current = path.join(current, part);
    if ((await lstat(current)).isSymbolicLink()) {
      fail("unsafe_path", "Remove symbolic links or junctions from the chart artifact path.");
    }
  }
  const canonical = await realpath(resolved);
  if (!samePath(canonical, resolved)) {
    fail("unsafe_path", "Use the canonical chart path without redirects or reparse points.");
  }
  return canonical;
}

async function inspectPaths(input) {
  exactObject(input, ["path", "outputRoot"]);
  const root = await canonicalNoLinks(input.outputRoot);
  if (path.basename(root).toLowerCase() !== "charts"
    || path.basename(path.dirname(root)).toLowerCase() !== "build"
    || !(await lstat(root)).isDirectory()) {
    fail("invalid_root", "outputRoot must be an existing canonical workspace build/charts directory.");
  }
  const file = await canonicalNoLinks(input.path);
  const relative = path.relative(root, file);
  const id = path.basename(file, ".html");
  if (!relative || relative.startsWith(`..${path.sep}`) || relative === ".."
    || path.isAbsolute(relative) || !ID.test(id) || path.extname(file) !== ".html") {
    fail("unsafe_path", "Select a generated 32-lowercase-hex .html artifact contained in outputRoot.");
  }
  const stat = await lstat(file);
  if (!stat.isFile() || stat.nlink !== 1) {
    fail("unsafe_path", "Select a regular generated HTML file, not a link or directory.");
  }
  if (stat.size > MAX_HTML_BYTES) {
    fail("chart_too_large", "Regenerate the chart below the 8 MiB HTML limit.");
  }
  return { path: file, outputRoot: root, chart_id: id, stat };
}

function attributes(tag) {
  const result = {};
  for (const match of tag.matchAll(/([a-zA-Z][\w-]*)\s*=\s*(?:"([^"]*)"|'([^']*)')/g)) {
    const key = match[1].toLowerCase();
    if (Object.hasOwn(result, key)) fail("invalid_html", "Regenerate HTML with unambiguous chart metadata.");
    result[key] = (match[2] ?? match[3])
      .replace(/&quot;/gi, "\"").replace(/&#(?:39|x27);|&apos;/gi, "'").replace(/&amp;/gi, "&");
  }
  return result;
}

export function validateHtml(bytes) {
  if (bytes.length > MAX_HTML_BYTES) fail("chart_too_large", "Regenerate the chart below the 8 MiB HTML limit.");
  let html;
  try { html = new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
  catch { fail("invalid_html", "Regenerate the chart as UTF-8 standalone HTML."); }
  const metas = [...html.matchAll(/<meta\b[^>]*>/gi)].map((match) => ({
    index: match.index, attrs: attributes(match[0]),
  })).filter(({ attrs }) => attrs["http-equiv"]?.toLowerCase() === "content-security-policy");
  if (metas.length !== 1) fail("invalid_html", "Regenerate the chart with its restrictive meta CSP.");
  const directives = new Map();
  for (const entry of (metas[0].attrs.content ?? "").split(";").filter((part) => part.trim())) {
    const [name, ...sources] = entry.trim().split(/\s+/);
    if (directives.has(name)) fail("invalid_html", "Regenerate the chart with a single restrictive CSP policy.");
    directives.set(name, sources);
  }
  const isNone = (sources) => sources?.length === 1 && sources[0] === "'none'";
  if (!isNone(directives.get("default-src")) || !isNone(directives.get("base-uri"))
    || !isNone(directives.get("form-action"))) {
    fail("invalid_html", "Regenerate the chart with default-src, base-uri, and form-action set to 'none'.");
  }
  const hashes = directives.get("script-src") ?? [];
  if (!hashes.length || !hashes.every((source) => /^'sha(?:256|384|512)-[A-Za-z0-9+/]+=*'$/.test(source))) {
    fail("invalid_html", "Regenerate the chart with hash-authorized inline scripts only.");
  }
  for (const [name, sources] of directives) {
    if (["default-src", "base-uri", "form-action", "script-src"].includes(name)) continue;
    const allowed = name === "style-src" ? ["'none'", "'unsafe-inline'"]
      : name === "img-src" ? ["'none'", "data:", "blob:"] : ["'none'"];
    if (!["style-src", "img-src", "connect-src", "font-src", "object-src", "frame-src",
      "worker-src", "media-src", "manifest-src", "child-src"].includes(name)
      || !sources.length || !sources.every((source) => allowed.includes(source))) {
      fail("invalid_html", "Regenerate the chart without remote sources or CSP overrides.");
    }
  }
  let payloadCount = 0;
  for (const script of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script\s*>/gi)) {
    if (script.index < metas[0].index) fail("invalid_html", "Place the chart CSP before all scripts.");
    const attrs = attributes(script[1]);
    if (/\bsrc\s*=/i.test(script[1])) fail("invalid_html", "Regenerate the chart with all scripts inline.");
    if (attrs.id === "sqlmem-chart-data" && attrs.type === "application/json") {
      let payload;
      try { payload = JSON.parse(script[2]); } catch { fail("invalid_html", "Regenerate the chart's JSON payload."); }
      if (!payload || payload.format !== "sqlmem-chart" || payload.version !== 1) {
        fail("invalid_html", "Use generated sqlmem-chart format version 1 HTML.");
      }
      payloadCount += 1;
    } else if (attrs.type !== "application/json") {
      if (!["sha256", "sha384", "sha512"].some((algorithm) =>
        hashes.includes(`'${algorithm}-${createHash(algorithm).update(script[2]).digest("base64")}'`))) {
        fail("invalid_html", "Regenerate the chart so inline scripts match its CSP hashes.");
      }
    }
  }
  if (payloadCount !== 1) fail("invalid_html", "Use generated HTML containing one sqlmem-chart-data version 1 payload.");
  return [...directives].map(([name, sources]) => `${name} ${sources.join(" ")}`).join("; ");
}

export async function readArtifact(input) {
  try {
    const artifact = await inspectPaths(input);
    const handle = await open(artifact.path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
    try {
      const before = await handle.stat();
      if (before.ino !== artifact.stat.ino || before.dev !== artifact.stat.dev || !before.isFile()) {
        fail("unsafe_path", "The chart changed during validation; regenerate or reopen it.");
      }
      const bytes = Buffer.alloc(Math.min(MAX_HTML_BYTES + 1, before.size + 1));
      let length = 0;
      while (length < bytes.length) {
        const { bytesRead } = await handle.read(bytes, length, bytes.length - length, null);
        if (!bytesRead) break;
        length += bytesRead;
      }
      const after = await handle.stat();
      const current = await inspectPaths(input);
      if (length !== after.size || before.size !== after.size || before.mtimeMs !== after.mtimeMs
        || current.stat.ino !== before.ino || current.stat.dev !== before.dev) {
        fail("unsafe_path", "The chart changed while reading; reopen the completed generated artifact.");
      }
      const body = bytes.subarray(0, length);
      const csp = validateHtml(body);
      return { path: artifact.path, outputRoot: artifact.outputRoot, chart_id: artifact.chart_id, body, csp };
    } finally { await handle.close(); }
  } catch (error) {
    if (error instanceof ChartError) throw error;
    fail("chart_unavailable", "Cannot read the chart. Generate an existing HTML artifact inside its build/charts root.");
  }
}

export function requestStatus(request, host) {
  if (!["GET", "HEAD"].includes(request.method)) return 405;
  if (request.url !== "/" && request.url !== "/download") return 404;
  const raw = request.rawHeaders;
  const count = (name) => raw.filter((_, index) => index % 2 === 0 && raw[index].toLowerCase() === name).length;
  if (count("host") !== 1 || request.headers.host !== host) return 403;
  if (count("origin") > 1 || (request.headers.origin !== undefined && request.headers.origin !== `http://${host}`)) return 403;
  if (request.headers["transfer-encoding"] || (request.headers["content-length"] && request.headers["content-length"] !== "0")) return 400;
  return 200;
}

export async function createViewer(input, {
  read = readArtifact, idleMs = 10 * 60 * 1000, lifetimeMs = 60 * 60 * 1000, onClose = () => {},
} = {}) {
  const registered = await read(input);
  const stableInput = { path: registered.path, outputRoot: registered.outputRoot };
  const sockets = new Set();
  let active = 0;
  let closed = false;
  let closePromise;
  let idleTimer;
  let lifetimeTimer;
  let host;
  const server = http.createServer({
    maxHeaderSize: 16 * 1024, requestTimeout: 5000, headersTimeout: 5000,
    connectionsCheckingInterval: 1000,
  }, async (request, response) => {
    response.setHeader("Cache-Control", "no-store");
    response.setHeader("Referrer-Policy", "no-referrer");
    response.setHeader("X-Content-Type-Options", "nosniff");
    response.setHeader("Cross-Origin-Resource-Policy", "same-origin");
    const reject = (status) => {
      response.writeHead(status, { "Content-Type": "text/plain; charset=utf-8", Connection: "close" });
      response.end(request.method === "HEAD" ? undefined : "Chart request rejected.");
    };
    const status = requestStatus(request, host);
    if (status !== 200) return reject(status);
    if (closed) return reject(410);
    if (active >= 8) return reject(503);
    active += 1;
    let finished = false;
    const finish = () => { if (!finished) { finished = true; active -= 1; } };
    response.once("close", finish);
    response.once("finish", finish);
    touch();
    try {
      const artifact = await read(stableInput);
      if (closed || response.destroyed) return;
      response.setHeader("Content-Type", "text/html; charset=utf-8");
      response.setHeader("Content-Security-Policy", artifact.csp);
      response.setHeader("Content-Length", artifact.body.length);
      if (request.url === "/download") {
        response.setHeader("Content-Disposition", `attachment; filename="${registered.chart_id}.html"`);
      }
      response.writeHead(200);
      response.end(request.method === "HEAD" ? undefined : artifact.body);
    } catch { if (!response.destroyed) reject(410); }
  });
  server.maxConnections = 32;
  server.keepAliveTimeout = 5000;
  server.on("connection", (socket) => {
    sockets.add(socket);
    socket.setTimeout(5000, () => socket.destroy());
    socket.once("close", () => sockets.delete(socket));
  });
  server.on("clientError", (_, socket) => socket.destroy());

  function touch() {
    clearTimeout(idleTimer);
    if (!closed) idleTimer = setTimeout(() => { void close(); }, idleMs).unref();
  }
  function close() {
    if (closePromise) return closePromise;
    closed = true;
    clearTimeout(idleTimer);
    clearTimeout(lifetimeTimer);
    closePromise = new Promise((resolve) => {
      server.close(() => resolve());
      for (const socket of sockets) socket.destroy();
    });
    onClose();
    return closePromise;
  }
  try {
    await new Promise((resolve, reject) => {
      server.once("error", reject);
      server.listen(0, "127.0.0.1", resolve);
    });
  } catch {
    await close();
    fail("viewer_unavailable", "Cannot start the loopback chart viewer; reopen the canvas.");
  }
  // Runtime errors must not print paths, data, or other private state.
  server.on("error", () => { void close(); });
  host = `127.0.0.1:${server.address().port}`;
  const url = `http://${host}/`;
  touch();
  lifetimeTimer = setTimeout(() => { void close(); }, lifetimeMs).unref();
  return {
    url,
    input: stableInput,
    chart_id: registered.chart_id,
    get closed() { return closed; },
    descriptor(download = false) {
      return { chart_id: registered.chart_id, path: registered.path, url: download ? `${url}download` : url };
    },
    async refresh() {
      if (closed) fail("viewer_closed", "The chart viewer expired; reopen the canvas with its artifact path.");
      await read(stableInput);
      touch();
      return this.descriptor();
    },
    close,
  };
}

export function createChartCanvasOptions(CanvasError) {
  const instances = new Map();
  const queues = new Map();
  let opening = 0;
  const keyOf = (ctx) => {
    if (typeof ctx?.instanceId !== "string" || !ctx.instanceId || ctx.instanceId.length > 256) {
      fail("invalid_instance", "Provide a non-empty canvas instanceId of at most 256 characters.");
    }
    return `${ctx.sessionId ?? ""}\0${ctx.instanceId}`;
  };
  const guarded = (operation) => async (ctx) => {
    try {
      const key = keyOf(ctx);
      if (!queues.has(key) && queues.size >= 32) fail("viewer_limit", "Wait for pending chart actions to finish.");
      const previous = queues.get(key) ?? Promise.resolve();
      const task = previous.catch(() => {}).then(() => operation(ctx, key));
      queues.set(key, task);
      try { return await task; }
      finally { if (queues.get(key) === task) queues.delete(key); }
    } catch (error) {
      throw new CanvasError(error instanceof ChartError ? error.code : "chart_unavailable",
        error instanceof ChartError ? error.message : "Chart viewer unavailable; regenerate the artifact and reopen.");
    }
  };
  const action = (name, description, inputSchema) => ({
    name, description, inputSchema,
    handler: guarded(async (ctx, key) => {
      if (ctx.actionName !== name) fail("invalid_action", "Use a declared chart action name.");
      exactObject(ctx.input, name === "show_chart" ? ["chart_id"] : []);
      const viewer = instances.get(key);
      if (!viewer || viewer.closed) fail("viewer_closed", "Open the canvas with a generated chart artifact first.");
      if (name === "show_chart" && (typeof ctx.input.chart_id !== "string"
        || !ID.test(ctx.input.chart_id) || ctx.input.chart_id !== viewer.chart_id)) {
        fail("chart_not_registered", "show_chart accepts only this instance's registered chart_id; open another artifact explicitly.");
      }
      await viewer.refresh();
      return viewer.descriptor(name === "download_html");
    }),
  });
  return {
    id: CANVAS_ID,
    displayName: "SQLMem Chart",
    description: "Display an existing standalone SQLMem ECharts or 3D chart without rerendering or database access.",
    inputSchema: INPUT_SCHEMA,
    actions: [
      action("refresh", "Revalidate the registered artifact and return its viewer descriptor.", EMPTY_SCHEMA),
      action("show_chart", "Return the current registered chart's viewer descriptor.", SHOW_SCHEMA),
      action("download_html", "Return the registered standalone HTML download descriptor.", EMPTY_SCHEMA),
    ],
    open: guarded(async (ctx, key) => {
      exactObject(ctx.input, ["path", "outputRoot"]);
      const old = instances.get(key);
      if (old && !old.closed && old.input.path === ctx.input.path && old.input.outputRoot === ctx.input.outputRoot) {
        await old.refresh();
        return { url: old.url, title: "SQLMem Chart" };
      }
      if (instances.size + opening >= 16) fail("viewer_limit", "Close an existing chart canvas before opening another.");
      opening += 1;
      try {
        let viewer;
        viewer = await createViewer(ctx.input, { onClose: () => {
          if (viewer && instances.get(key) === viewer) instances.delete(key);
        } });
        instances.set(key, viewer);
        if (old) await old.close();
        return { url: viewer.url, title: "SQLMem Chart" };
      } finally { opening -= 1; }
    }),
    onClose: guarded(async (_, key) => {
      const viewer = instances.get(key);
      instances.delete(key);
      if (viewer) await viewer.close();
    }),
  };
}
