/**
 * Dashboard Main Controller
 * Bootstraps the app, handles tab switching, health check, and overview stats.
 */

const App = {
  currentTab: 'overview',
  _toastTimer: null,
  _healthTimer: null,
  _chartData: null,

  async init() {
    // Try to restore session
    const user = Auth.init();
    if (user) {
      this.showApp(user);
    } else {
      Auth.setupLoginForm();
    }
  },

  showApp(user) {
    // Hide login, show app
    document.getElementById('login-overlay').classList.add('hidden');
    document.getElementById('app').classList.remove('hidden');

    // Set user info in sidebar
    document.getElementById('user-name').textContent = user.name || 'Admin';
    document.getElementById('user-avatar').textContent = (user.name || 'A')[0].toUpperCase();

    // Logout button
    document.getElementById('logout-btn').addEventListener('click', () => Auth.logout());

    // Refresh button
    document.getElementById('refresh-btn').addEventListener('click', () => this.refreshCurrentTab());

    // Contacts search
    Contacts.setupSearch();

    // Messages search
    Messages.setupSearch();

    // Add Personality button
    document.getElementById('add-personality-btn').addEventListener('click', () => Personalities.openCreate());

    // Logs setup
    Logs.setup();

    // Nav click events
    document.querySelectorAll('.nav-item').forEach(el => {
      el.addEventListener('click', (e) => {
        e.preventDefault();
        this.switchTab(el.dataset.tab);
      });
    });

    // Close modals on overlay click
    document.getElementById('contact-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) Contacts.closeModal();
    });
    document.getElementById('personality-modal').addEventListener('click', (e) => {
      if (e.target === e.currentTarget) Personalities.closeModal();
    });

    // Load initial data
    this.loadOverview();
    this.startHealthCheck();
    this.switchTab('overview');
  },

  switchTab(tab) {
    this.currentTab = tab;

    // Update nav active state
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.dataset.tab === tab);
    });

    // Show/hide sections
    document.querySelectorAll('.tab-section').forEach(el => {
      el.classList.toggle('active', el.id === `tab-${tab}`);
      el.classList.toggle('hidden', el.id !== `tab-${tab}`);
    });

    // Update page title
    const titles = {
      overview:     'Overview',
      contacts:     'Contacts',
      messages:     'Messages',
      personalities:'Personalities',
      'ai-settings':'AI Settings',
      logs:         'Logs',
    };
    document.getElementById('page-title').textContent = titles[tab] || tab;
    document.getElementById('breadcrumb').textContent = `Dashboard / ${titles[tab] || tab}`;

    // Load tab data
    switch (tab) {
      case 'overview':     this.loadOverview(); break;
      case 'contacts':     Contacts.load(); break;
      case 'messages':     Messages.loadConversationList(); break;
      case 'personalities':Personalities.load(); break;
      case 'ai-settings':  AiSettings.load(); break;
      case 'logs':         Logs.load(); break;
    }
  },

  refreshCurrentTab() {
    this.switchTab(this.currentTab);
  },

  // Navigate to messages tab and open a specific contact's conversation
  viewMessages(contactId, name) {
    this.switchTab('messages');
    setTimeout(() => {
      Messages.openConversation(contactId, name);
    }, 300);
  },

  // ── OVERVIEW ──────────────────────────────────────────────
  async loadOverview() {
    try {
      const [statsRes, aiRes] = await Promise.allSettled([
        Api.stats(7),
        Api.aiSettings(),
      ]);

      if (statsRes.status === 'fulfilled') {
        const d = statsRes.value.data;
        const msgs = d.messages || {};
        const contacts = d.contacts || {};

        document.getElementById('val-total-contacts').textContent = contacts.total ?? '0';
        document.getElementById('val-total-messages').textContent = msgs.total ?? '0';
        document.getElementById('val-ai-contacts').textContent = contacts.ai_enabled ?? '0';

        const el = document.getElementById('trend-messages');
        if (el) {
          el.textContent = `${msgs.inbound||0} in · ${msgs.outbound||0} out`;
        }

        // Update contacts badge
        const badge = document.getElementById('contacts-badge');
        if (badge) badge.textContent = contacts.total || '0';

        // Draw chart
        this._drawChart(d.daily_counts || []);
      }

      if (aiRes.status === 'fulfilled') {
        const provName = aiRes.value.data?.active_provider || '—';
        const provMeta = AiSettings.PROVIDER_META?.[provName];
        document.getElementById('val-provider').textContent =
          provMeta ? provMeta.name.split(' ')[0] : provName;
      }
    } catch (e) {
      console.error('Overview load error', e);
    }
  },

  _drawChart(dailyCounts) {
    const canvas = document.getElementById('messages-chart');
    if (!canvas) return;

    const emptyEl = document.getElementById('chart-empty');

    if (!dailyCounts.length) {
      if (emptyEl) emptyEl.classList.remove('hidden');
      return;
    }
    if (emptyEl) emptyEl.classList.add('hidden');

    // Simple canvas bar chart (no external libraries)
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width  = rect.width * dpr;
    canvas.height = rect.height * dpr;
    canvas.style.width  = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.scale(dpr, dpr);

    const W = rect.width;
    const H = rect.height;
    const PAD = { top: 20, right: 16, bottom: 40, left: 40 };
    const chartW = W - PAD.left - PAD.right;
    const chartH = H - PAD.top - PAD.bottom;

    // Prepare last 7 data points
    const data = dailyCounts.slice(-7);
    const maxVal = Math.max(...data.map(d => d.count || 0), 1);

    ctx.clearRect(0, 0, W, H);

    // Grid lines
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = PAD.top + (chartH / 4) * i;
      ctx.beginPath();
      ctx.moveTo(PAD.left, y);
      ctx.lineTo(PAD.left + chartW, y);
      ctx.stroke();
    }

    // Y axis labels
    ctx.fillStyle = 'rgba(255,255,255,0.3)';
    ctx.font = `${11 * dpr / dpr}px Inter, sans-serif`;
    ctx.textAlign = 'right';
    for (let i = 0; i <= 4; i++) {
      const val = Math.round(maxVal * (1 - i / 4));
      const y = PAD.top + (chartH / 4) * i;
      ctx.fillText(val, PAD.left - 6, y + 4);
    }

    const barW = Math.max(8, chartW / data.length * 0.5);
    const spacing = chartW / data.length;

    // Draw gradient bars
    data.forEach((d, i) => {
      const x = PAD.left + spacing * i + spacing / 2 - barW / 2;
      const barH = (d.count / maxVal) * chartH;
      const y = PAD.top + chartH - barH;

      const grad = ctx.createLinearGradient(0, y, 0, y + barH);
      grad.addColorStop(0, 'rgba(37,211,102,0.85)');
      grad.addColorStop(1, 'rgba(18,140,126,0.3)');
      ctx.fillStyle = grad;
      ctx.beginPath();
      ctx.roundRect(x, y, barW, barH, 4);
      ctx.fill();

      // X axis labels (day)
      const id = d._id || {};
      const label = id.day != null ? `${id.month}/${id.day}` : String(i + 1);
      ctx.fillStyle = 'rgba(255,255,255,0.3)';
      ctx.textAlign = 'center';
      ctx.fillText(label, x + barW / 2, PAD.top + chartH + 20);
    });
  },

  // ── HEALTH CHECK ──────────────────────────────────────────
  async checkHealth() {
    const dotEl  = document.querySelector('.health-dot');
    const textEl = document.querySelector('.health-text');
    try {
      const data = await Api.health();
      const healthy = data.status === 'healthy';
      dotEl.className  = `health-dot ${healthy ? 'healthy' : 'degraded'}`;
      textEl.textContent = healthy ? 'Healthy' : 'Degraded';
    } catch {
      dotEl.className  = 'health-dot down';
      textEl.textContent = 'Offline';
    }
  },

  startHealthCheck() {
    this.checkHealth();
    this._healthTimer = setInterval(() => this.checkHealth(), 30000);
  },

  // ── TOAST ────────────────────────────────────────────────
  toast(msg, type = 'success') {
    const el  = document.getElementById('toast');
    const msgEl = document.getElementById('toast-message');
    msgEl.textContent = msg;
    el.style.borderColor = type === 'error'
      ? 'rgba(239,68,68,0.4)'
      : 'rgba(37,211,102,0.3)';
    el.classList.remove('hidden');
    clearTimeout(this._toastTimer);
    this._toastTimer = setTimeout(() => el.classList.add('hidden'), 3000);
  },
};

// Bootstrap
document.addEventListener('DOMContentLoaded', () => App.init());
