// Expander Card - 占位符版本（原HACS组件缺失）
// 防止页面加载404错误

class ExpanderCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = config || {};
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    this.updateContent();
  }

  updateContent() {
    const container = this.shadowRoot.getElementById('container');
    if (!container) return;

    const title = this.config.title || '';
    
    let html = '';
    
    if (title) {
      html += `<h3 style="margin:0;padding:10px;font-size:14px;font-weight:600;cursor:pointer;color:var(--primary-text-color);" onclick="this.nextElementSibling.style.display=this.nextElementSibling.style.display==='none'?'block':'none'">${title} ▼</h3>`;
    }
    
    html += `<div style="padding:0 10px 10px;"><slot></slot></div>`;
    
    container.innerHTML = html;
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        #container { padding: 0; margin: 0; }
      </style>
      <div id="container"></div>
    `;
  }

  getCardSize() { return 1; }

  static getStubConfig() {
    return { title: "Expander" };
  }
}

customElements.define('expander-card', ExpanderCard);

console.log('[Expander Card] 占位符版本已加载 (v1.0)');
