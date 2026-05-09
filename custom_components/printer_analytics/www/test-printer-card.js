﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿﻿
/**
 * Printer Analytics Card - 最小化测试版
 * 用于诊断配置错误问题
 */
class TestPrinterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = config;
    if (!config) {
      throw new Error("配置为空");
    }
    if (!config.print_history) {
      throw new Error("缺少print_history配置");
    }
    this.render();
  }

  set hass(hass) {
    this._hass = hass;
    if (this.config) this.updateData();
  }

  updateData() {
    const container = this.shadowRoot.getElementById('card');
    if (!container || !this._hass || !this.config) return;

    try {
      const historyEntity = this._hass.states[this.config.print_history];
      let html = '<div style="padding:20px;font-family:sans-serif;">';
      html += `<h2 style="color:#03a9f4;margin-bottom:15px;">${this.config.title || 'Printer Analytics'}</h2>`;
      html += '<div style="background:#f5f5f5;padding:15px;border-radius:8px;">';
      
      if (historyEntity) {
        html += `<p>✅ 实体存在: <b>${this.config.print_history}</b></p>`;
        html += `<p>状态: <b>${historyEntity.state}</b></p>`;
        
        // 尝试获取历史数据
        const history = historyEntity.attributes?.history;
        if (Array.isArray(history) && history.length > 0) {
          html += `<p>历史记录数: <b>${history.length}</b> 条</p>`;
          html += `<p style="color:green">🎉 数据加载成功！</p>`;
        } else {
          html += `<p style="color:orange">⚠️ 历史数据为空或格式异常</p>`;
          html += `<pre style="font-size:12px;background:#fff;padding:10px;margin-top:10px;border-radius:4px;">${JSON.stringify(historyEntity.attributes).substring(0, 500)}</pre>`;
        }
      } else {
        html += `<p style="color:red"><b>❌ 实体不存在!</b></p>`;
        html += `<p>请检查实体ID: <code>${this.config.print_history}</code></p>`;
      }
      
      html += '</div>';
      
      // 显示所有配置的实体
      html += '<details style="margin-top:15px;"><summary style="cursor:pointer;color:#666;">调试信息</summary><pre style="font-size:11px;background:#fff;padding:10px;">';
      html += `配置项:\n${JSON.stringify(this.config, null, 2)}</pre></details>';
      
      html += '</div>';
      container.innerHTML = html;
    } catch (error) {
      console.error('TestPrinterCard Error:', error);
      container.innerHTML = `<div style="color:red;padding:20px;"><b>渲染错误:</b><br><pre>${error.message}\n\n${error.stack}</pre></div>`;
    }
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
      </style>
      <div id="card">
        <div style="padding:20px;text-align:center;color:#999;">
          加载中...
        </div>
      </div>
    `;
  }

  getCardSize() { return 6; }

  static getStubConfig() {
    return { title: "测试", print_history: "" };
  }
}

customElements.define('test-printer-card', TestPrinterCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'test-printer-card',
  name: 'Test Printer Card',
  description: 'Diagnostic card for Printer Analytics'
});
