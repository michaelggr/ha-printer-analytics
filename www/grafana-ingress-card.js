/**
 * grafana-ingress-card.js
 * 在 Lovelace 里直接嵌入 Grafana 面板 (走 HA Supervisor ingress, 无需写死 token, 不会 401)
 *
 * 用法:
 *   type: custom:grafana-ingress-card
 *   grafana_slug: a0d7b954_grafana        # 加载项 slug
 *   dashboard_path: d/a67f2s/xxx?kiosk    # 可选, Grafana 内部路径
 *   aspect_ratio: 100%                    # 可选, 默认 100%
 *
 * 原理:
 *   Supervisor ingress 的地址是 /api/hassio_ingress/<token>/ ,
 *   token 由 supervisor/api 的 addon info 接口给出 (ingress_url);
 *   但 ingress 本身用 cookie 鉴权, iframe 无法携带 Authorization 头,
 *   所以还要通过 supervisor/api 的 /ingress/session 拿会话并写入
 *   ingress_session cookie, 否则一律 401: Unauthorized。
 *   会话有有效期, 卡片每 5 分钟静默续期一次。
 */

const INGRESS_COOKIE_PATH = "/api/hassio_ingress";
const SESSION_RENEW_MS = 5 * 60 * 1000;

class GrafanaIngressCard extends HTMLElement {
  constructor() {
    super();
    // 只创建一次 shadow root, 避免重复 attachShadow 抛 NotSupportedError
    this.attachShadow({ mode: "open" });
    this._iframe = null;
    this._started = false;
  }

  setConfig(config) {
    if (!config.grafana_slug) {
      throw new Error("grafana-ingress-card 需要 grafana_slug");
    }
    this._config = config;
    this._aspect = config.aspect_ratio || "100%";

    // 首次渲染骨架
    if (!this._wrap) {
      this._build();
    }
    // 配置变化时重建 iframe
    if (this._started) {
      this._refresh();
    }
  }

  set hass(hass) {
    this._hass = hass;
    // hass 会频繁更新, 只在首次拿到时启动
    if (!this._started && this._config && hass) {
      this._started = true;
      this._refresh();
      // ingress 会话有有效期, 定时静默续期, 避免用着用着变 401
      this._renewTimer = window.setInterval(
        () => this._renewSession(),
        SESSION_RENEW_MS
      );
    }
  }

  disconnectedCallback() {
    // 卡片从 DOM 移除时停止续期, 防止定时器泄漏
    if (this._renewTimer) {
      window.clearInterval(this._renewTimer);
      this._renewTimer = null;
    }
  }

  /**
   * 建立 ingress 会话: supervisor/api 拿 session, 再写入 cookie。
   * iframe 导航无法带 Authorization 头, 只能依赖这个 cookie。
   */
  async _ensureIngressSession() {
    const res = await this._hass.callWS({
      type: "supervisor/api",
      endpoint: "/ingress/session",
      method: "post",
    });
    if (!res || !res.session) {
      throw new Error("未获取到 ingress 会话 (ingress/session 返回空)");
    }
    document.cookie =
      "ingress_session=" +
      res.session +
      "; path=" +
      INGRESS_COOKIE_PATH +
      "; SameSite=Lax";
    return res.session;
  }

  /** 静默续期: 只刷新 cookie, 不重载 iframe */
  async _renewSession() {
    if (!this._hass) return;
    try {
      await this._ensureIngressSession();
    } catch (err) {
      console.warn("[grafana-ingress-card] ingress 会话续期失败:", err);
    }
  }

  _build() {
    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; width: 100%; }
      .wrap { width: 100%; padding-top: ${this._aspect}; position: relative; }
      iframe {
        position: absolute; inset: 0; width: 100%; height: 100%;
        border: 0; background: #111;
      }
      .tip { color: var(--secondary-text-color, #888); padding: 16px; font-size: 14px; }
    `;
    this.shadowRoot.appendChild(style);

    this._wrap = document.createElement("div");
    this._wrap.className = "wrap";
    this.shadowRoot.appendChild(this._wrap);

    this._tip = document.createElement("div");
    this._tip.className = "tip";
    this._tip.textContent = "加载 Grafana 中...";
    this.shadowRoot.appendChild(this._tip);
  }

  async _refresh() {
    if (!this._hass || !this._config) return;
    const slug = this._config.grafana_slug;
    const path = (this._config.dashboard_path || "").replace(/^\//, "");

    try {
      // supervisor/api 走 websocket, 自动带上当前用户凭证
      const info = await this._hass.callWS({
        type: "supervisor/api",
        endpoint: `/addons/${slug}/info`,
        method: "get",
      });
      const base = info && info.ingress_url;
      if (!base) throw new Error("加载项未开启 ingress 或返回无 ingress_url");

      // 关键: 先建立 ingress 会话并写 cookie, 否则 iframe 请求会被 401 拦截
      await this._ensureIngressSession();

      // Grafana 面板内部路径 (无 kiosk 时补上, 隐藏顶部导航)
      let src = base + path;
      if (path && !path.includes("kiosk")) {
        src += path.includes("?") ? "&kiosk" : "?kiosk";
      }

      if (!this._iframe) {
        this._iframe = document.createElement("iframe");
        this._iframe.setAttribute("allow", "fullscreen");
        this._wrap.appendChild(this._iframe);
      }
      this._iframe.src = src;
      if (this._tip) {
        this._tip.remove();
        this._tip = null;
      }
    } catch (err) {
      console.error("[grafana-ingress-card] 加载失败:", err);
      if (this._tip) {
        this._tip.textContent = "Grafana 加载失败: " + (err.message || err);
      }
    }
  }

  getCardSize() {
    return 8;
  }
}

customElements.define("grafana-ingress-card", GrafanaIngressCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "grafana-ingress-card",
  name: "Grafana Ingress Card",
  description: "嵌入 Grafana 面板, 动态获取 ingress 地址, 不会 401",
});
