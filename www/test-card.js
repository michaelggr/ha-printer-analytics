class TestPrinterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
  }

  setConfig(config) {
    this.config = config;
    this.render();
  }

  render() {
    this.shadowRoot.innerHTML = `
      <style>
        .card {
          padding: 16px;
          background: white;
          border-radius: 8px;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
      </style>
      <div class="card">
        <h2>${this.config.title || '测试卡片'}</h2>
        <p>这是一个测试卡片</p>
      </div>
    `;
  }

  getCardSize() { return 1; }
}

customElements.define('test-printer-card', TestPrinterCard);
