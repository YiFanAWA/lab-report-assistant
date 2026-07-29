/**
 * 流式 SSE 请求基础 URL。
 *
 * 根因：Vite 6 dev server 代理对 chunked SSE 响应存在固有缓冲——会把整个响应
 * 缓冲到后端关闭连接才一次性返回，导致前端 fetch 等不到响应头而 net::ERR_ABORTED。
 * 配置级修复（server.compress:false / 显式 proxy 配置 / selfHandleResponse 手动 pipe）
 * 均已实测无效，缓冲发生在 Vite 中间件链更深层。
 *
 * 修复：dev 环境下流式请求直连后端（绕过 Vite 代理），由 VITE_API_BASE_URL 指定主机。
 * 生产环境（nginx 同源 + X-Accel-Buffering: no）留空，使用相对 /api 走 nginx 代理。
 *
 * 后端 app/main.py 已配置 CORS allow_origins=["http://localhost:5173"]，
 * dev 下浏览器直连 http://localhost:8001 不会被跨域拒绝。
 *
 * 仅用于流式 SSE 端点；非流式请求继续使用各自 api.ts 里的 BASE="/api"
 * （走 Vite 代理，无 chunked 流式缓冲问题）。
 */
export const STREAMING_BASE: string =
  ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "") + "/api";
