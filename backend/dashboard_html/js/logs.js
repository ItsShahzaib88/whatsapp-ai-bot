/**
 * Logs Tab — structured log viewer
 */

const Logs = {
  level: '',

  async load() {
    const container = document.getElementById('logs-container');
    container.innerHTML = '<div class="loading-state">Loading logs...</div>';
    try {
      const res = await Api.logs(this.level || null, 1, 200);
      const logs = res.data || [];
      this.render(logs);
    } catch {
      container.innerHTML = '<div class="loading-state">Error loading logs — collection may be empty</div>';
    }
  },

  render(logs) {
    const container = document.getElementById('logs-container');
    if (!logs.length) {
      container.innerHTML = '<div class="loading-state">No logs found</div>';
      return;
    }
    container.innerHTML = logs.map(log => {
      const time = log.created_at
        ? new Date(log.created_at).toLocaleString('en-US', {
            month:'short', day:'2-digit',
            hour:'2-digit', minute:'2-digit', second:'2-digit'
          })
        : '—';
      const level = log.level || 'INFO';
      const msg = (log.message || log.action || JSON.stringify(log)).slice(0, 300);
      return `
        <div class="log-entry">
          <span class="log-time">${time}</span>
          <span class="log-level ${level}">${level}</span>
          <span class="log-message">${this._esc(msg)}</span>
        </div>`;
    }).join('');
    // Auto-scroll to bottom for newest logs
    container.scrollTop = container.scrollHeight;
  },

  setup() {
    document.getElementById('log-level-filter').addEventListener('change', (e) => {
      this.level = e.target.value;
      this.load();
    });
    document.getElementById('refresh-logs-btn').addEventListener('click', () => this.load());
  },

  _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
  },
};
