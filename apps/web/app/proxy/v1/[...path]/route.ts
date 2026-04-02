import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

/** 仅主机 + 端口，勿带 /api/v1（否则会拼成双段路径导致上游 404） */
function backendOrigin(): string {
  let b = (process.env.API_PROXY_ORIGIN || "http://127.0.0.1:8000").trim().replace(/\/$/, "");
  b = b.replace(/\/api\/v1$/i, "");
  return b;
}

const DROP_REQ = new Set([
  "connection",
  "content-length",
  "host",
  "keep-alive",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade"
]);

const DROP_RES = new Set([
  "connection",
  "content-encoding",
  "content-length",
  "keep-alive",
  "transfer-encoding",
  "trailer"
]);

function forwardRequestHeaders(incoming: Headers): Headers {
  const out = new Headers();
  incoming.forEach((value, key) => {
    if (!DROP_REQ.has(key.toLowerCase())) out.append(key, value);
  });
  return out;
}

function forwardResponseHeaders(incoming: Headers): Headers {
  const out = new Headers();
  incoming.forEach((value, key) => {
    if (!DROP_RES.has(key.toLowerCase())) out.append(key, value);
  });
  return out;
}

type ParamsInput = { path: string[] } | Promise<{ path: string[] }>;

async function segmentsFromCtx(params: ParamsInput): Promise<string[]> {
  const p = await Promise.resolve(params);
  const path = p?.path;
  return Array.isArray(path) ? path : [];
}

async function proxy(req: NextRequest, pathSegments: string[]): Promise<NextResponse> {
  const subpath = pathSegments.join("/");
  if (!subpath) {
    return NextResponse.json({ detail: "代理路径为空" }, { status: 400 });
  }

  const backend = backendOrigin();
  const target = `${backend}/api/v1/${subpath}${req.nextUrl.search}`;

  const init: RequestInit = {
    method: req.method,
    headers: forwardRequestHeaders(req.headers)
  };

  if (req.method !== "GET" && req.method !== "HEAD") {
    init.body = await req.arrayBuffer();
  }

  let upstream: Response;
  try {
    upstream = await fetch(target, { ...init, signal: AbortSignal.timeout(120_000) });
  } catch {
    return NextResponse.json(
      { detail: `无法连接后端 ${backend}，请在本机启动 FastAPI（默认端口 8000）。` },
      { status: 502 }
    );
  }

  const headers = forwardResponseHeaders(upstream.headers);
  return new NextResponse(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers
  });
}

type Ctx = { params: ParamsInput };

export async function GET(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function PUT(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function DELETE(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function OPTIONS(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
export async function HEAD(req: NextRequest, ctx: Ctx) {
  return proxy(req, await segmentsFromCtx(ctx.params));
}
