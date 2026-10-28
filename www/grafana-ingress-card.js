/**
 * grafana-ingress-card.js
 * 动态拿 HA ingress token 嵌 Grafana dashboard, 解决写死 token 过期 401 问题
 *
 * 用法 (在 ui-energy.yaml view 里):
 *   type: custom:grafana-ingress-card
 *   grafana_slug: a0d7b954_grafana   # Grafana addon slug (HA Supervisor 管理的)
 *   dashboard_path: d/a67f2s/e883bd-e6ba90-e8b4a6-e58d95-e79b91-e68ea7?kiosk
 *   aspect_ratio: 100%              # 可选, 默认 100%
 */

class GrafanaIngressCard extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    if (!this._iframe && hass) {
      this._build();
      this._refresh();
    }
  }

  setConfig(config) {
    // grafana_slug + dashboard_path 必填
    if (!config.grafana_slug || !config.dashboard_path) {
      throw new Error("grafana-ingress-card 需要 grafana_slug + dashboard_path");
    }
    this._config = config;
    // aspect_ratio 默认铺满
    this._aspect = config.aspect_ratio || "100%";
    if (this._iframe) {
      // config 变了重建
      this.shadowRoot.innerHTML = "";
      this._iframe = null;
      this._build();
      this._refresh();
    }
  }

  _build() {
    // 利用 HA lovelace 标准 shadow DOM 结构
    const shadow = this.attachShadow({ mode: "open" });

    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; width: 100%; }
      .wrap { width: 100%; padding-top: ${this._aspect}; position: relative; }
      iframe {
        position: absolute; inset: 0; width: 100%; height: 100%;
        border: 0; background: #000;
      }
      .loading { color: #888; padding: 16px; font-size: 14px; }
      .error { color: #f55; padding: 16px; font-size: 14px; }
    `;
    shadow.appendChild(style);

    this._wrap = document.createElement("div");
    this._wrap.className = "wrap";
    shadow.appendChild(this._wrap);

    // 先放 loading 文字
    this._loading = document.createElement("div");
    this._loading.className = "loading";
    this._loading.textContent = "加载 Grafana 中...";
    shadow.appendChild(this._loading);
  }

  async _refresh() {
    if (!this._hass || !this._config) return;
    const slug = this._config.grafana_slug;
    const path = this._config.dashboard_path;

    try {
      // REST endpoint: /api/hassio/ingress_token?addon=<slug>
      // (HA 前端 hassio-ingress.js 官方也是这么拿 token 的)
      const url = this._hass.hassUrl(`/api/hassio/ingress_token?addon=${slug}`);
      const resp = await fetch(url, {
        headers: {
          // 用当前用户 session 或 Long-Lived Access Token 都行
          Authorization: this._hass.auth.accessToken
            ? `Bearer ${this._hass.auth.accessToken}`
            : "",
        },
        credentials: "same-origin",
      });
      if (!resp.ok) throw new Error(`HTTP ${resp.status} from ingress_token`);
      const data = await resp.json();
      const token = data.token || data.ingress_token || "";
      if (!token) throw new Error("响应无 token 字段: " + JSON.stringify(data));

      const base = this._hass.hassUrl(`/api/hassio_ingress/${token}/`);
      const fullUrl = base + path.replace(/^\//, "");

      // 创建/更新 iframe
      if (!this._iframe) {
        this._iframe = document.createElement("iframe");
        this._iframe.setAttribute("allow", "fullscreen");
        this._iframe.setAttribute("loading", "lazy");
        this._wrap.appendChild(this._iframe);
      }
      this._iframe.src = fullUrl;
      this._loading.remove();
    } catch (err) {
      console.error("[grafana-ingress-card] 拿 ingress token 失败:", err);
      if (this._loading) {
        this._loading.className = "error";
        this._loading.textContent =
          "Grafana ingress 加载失败: " + (err.message || err);
      }
    }
  }

  // Lovelace 标准: 支持 size
  getCardSize() { return 8; }
}

customElements.define("grafana-ingress-card", GrafanaIngressCard);

// 兼容 custom: 前缀
window.customCards = window.customCards || [];
window.customCards.push({
  type: "grafana-ingress-card",
  name: "Grafana Ingress Card",
  description: "动态拿 ingress token 嵌 Grafana dashboard, 不会因 token 过期 401",
});
