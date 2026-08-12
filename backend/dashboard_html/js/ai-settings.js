/**
 * AI Settings Tab — provider selection and info
 */

const AiSettings = {
  activeProvider: null,
  availableProviders: [],

  PROVIDER_META: {
    gemini:      { icon: '✨', name: 'Google Gemini',  desc: 'Free tier · gemini-2.0-flash · Best for general use' },
    groq:        { icon: '⚡', name: 'Groq (Llama)',   desc: 'Ultra-fast LPU · Free 14K req/day · llama-3.3-70b' },
    openai:      { icon: '🤖', name: 'OpenAI GPT',     desc: 'GPT-4o-mini · Paid · Most capable' },
    openrouter:  { icon: '🔀', name: 'OpenRouter',     desc: '100+ models · Claude, Llama · Pay per use' },
    together:    { icon: '🤝', name: 'Together AI',    desc: 'Open source models · Affordable pricing' },
  },

  async load() {
    const grid = document.getElementById('providers-grid');
    grid.innerHTML = '<div class="loading-state">Loading providers...</div>';
    try {
      const res = await Api.aiSettings();
      this.activeProvider   = res.data.active_provider;
      this.availableProviders = res.data.available_providers;
      this.render();
    } catch {
      grid.innerHTML = '<div class="loading-state">Error — no AI providers configured</div>';
    }
  },

  render() {
    const grid = document.getElementById('providers-grid');
    if (!this.availableProviders.length) {
      grid.innerHTML = `
        <div style="padding:20px;color:var(--accent-orange);font-size:0.875rem">
          No AI providers configured. Add at least one API key in your .env file and restart.
        </div>`;
      return;
    }
    grid.innerHTML = this.availableProviders.map(name => {
      const meta = this.PROVIDER_META[name] || { icon: '🔧', name, desc: 'Custom provider' };
      const isActive = name === this.activeProvider;
      return `
        <button class="provider-btn ${isActive ? 'active' : ''}" onclick="AiSettings.setProvider('${name}')">
          <div class="provider-icon-box" style="background:rgba(255,255,255,0.07);font-size:1.3rem">
            ${meta.icon}
          </div>
          <div class="provider-details">
            <div class="provider-name">${meta.name}</div>
            <div class="provider-desc">${meta.desc}</div>
          </div>
          ${isActive ? '<span class="provider-active-badge">Active</span>' : ''}
        </button>`;
    }).join('');
  },

  async setProvider(name) {
    if (name === this.activeProvider) return;
    try {
      await Api.setProvider(name);
      this.activeProvider = name;
      this.render();
      App.toast(`Switched to ${this.PROVIDER_META[name]?.name || name}`);
      // Refresh the stat card
      const valEl = document.getElementById('val-provider');
      if (valEl) valEl.textContent = (this.PROVIDER_META[name]?.name || name).split(' ')[0];
    } catch {
      App.toast('Failed to switch provider', 'error');
    }
  },
};
