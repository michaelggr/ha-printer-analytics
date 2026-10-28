/**
 * ingress-session-keeper.js
 * 全局维持 Supervisor ingress 会话 cookie (ingress_session)。
 *
 * 背景:
 *   addon 的 ingress 页面 (/api/hassio_ingress/<token>/...) 用 cookie 鉴权,
 *   iframe / 新标签导航无法携带 Authorization 头, 没有这个 cookie 就返回
 *   "401: Unauthorized"。HA 前端在某些情况下不会自动建立该会话,
 *   于是所有加载项的 Web UI (Grafana / MariaDB 等) 都会 401。
 *
 * 做法:
 *   页面加载后通过 window.hassConnection 调 supervisor/api 的 /ingress/session,
 *   拿到会话写入 cookie, 之后每 5 分钟静默续期。
 *
 * 注册:
 *   configuration.yaml -> frontend.extra_module_url, 对所有前端页面生效
 *   (含 Supervisor 面板, 不只是 Lovelace 看板)。
 */

const INGRESS_COOKIE_PATH = "/api/hassio_ingress";
const RENEW_MS = 5 * 60 * 1000;

/** 建立/续期 ingress 会话, 成功返回 true */
async function ensureIngressSession() {
  // 登录页等无会话场景没有连接对象, 直接跳过
  if (!window.hassConnection) return false;

  const { conn } = await window.hassConnection;
  if (!conn) return false;

  const res = await conn.sendMessagePromise({
    type: "supervisor/api",
    endpoint: "/ingress/session",
    method: "post",
  });
  if (!res || !res.session) return false;

  // path 限定在 ingress 前缀下, 避免污染其他请求
  document.cookie =
    "ingress_session=" + res.session + "; path=" + INGRESS_COOKIE_PATH + "; SameSite=Lax";
  return true;
}

async function tick() {
  try {
    await ensureIngressSession();
  } catch (err) {
    // 未登录 / 无 supervisor 权限时失败属正常, 下个周期再试
    console.debug("[ingress-session] 建立或续期失败:", err);
  }
  window.setTimeout(tick, RENEW_MS);
}

// 延迟 1 秒启动, 等前端登录态与 hassConnection 就绪
window.setTimeout(tick, 1000);
