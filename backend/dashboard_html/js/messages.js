/**
 * Messages Tab — conversation list and viewer
 */

const Messages = {
  contacts: [],
  activeId: null,
  activeName: null,
  _searchTimer: null,

  async loadConversationList() {
    const listEl = document.getElementById('conversation-list');
    listEl.innerHTML = '<div class="conv-loading">Loading...</div>';
    try {
      const res = await Api.contacts(1, 50);
      this.contacts = (res.data || []).filter(c => (c.total_messages_received + c.total_messages_sent) > 0
        || true); // show all
      this.renderList(this.contacts);
    } catch {
      listEl.innerHTML = '<div class="conv-loading">Error loading</div>';
    }
  },

  renderList(contacts) {
    const listEl = document.getElementById('conversation-list');
    if (!contacts.length) {
      listEl.innerHTML = '<div class="conv-loading">No contacts yet</div>';
      return;
    }
    listEl.innerHTML = contacts.map(c => {
      const initial = (c.name || c.phone_number || '?')[0].toUpperCase();
      const lastSeen = c.last_message_at
        ? new Date(c.last_message_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
        : '';
      const totalMsgs = (c.total_messages_received||0) + (c.total_messages_sent||0);
      return `
        <div class="conv-item ${c.id===this.activeId?'active':''}" onclick="Messages.openConversation('${c.id}','${this._esc(c.name||c.phone_number)}')">
          <div style="display:flex;justify-content:space-between;align-items:flex-start">
            <div class="conv-name">${this._esc(c.name || c.phone_number)}</div>
            <span class="conv-time">${lastSeen}</span>
          </div>
          <div class="conv-preview">${totalMsgs} messages | ${c.phone_number}</div>
        </div>`;
    }).join('');
  },

  async openConversation(id, name) {
    this.activeId = id;
    this.activeName = name;

    // Update active state in list
    document.querySelectorAll('.conv-item').forEach(el => el.classList.remove('active'));
    event?.target?.closest('.conv-item')?.classList.add('active');

    const viewEl = document.getElementById('messages-view');
    viewEl.innerHTML = `
      <div class="messages-header">
        <div class="contact-avatar" style="width:36px;height:36px;font-size:0.85rem">${name[0].toUpperCase()}</div>
        <div>
          <div class="messages-header-name">${this._esc(name)}</div>
          <div class="messages-header-phone">Loading messages...</div>
        </div>
      </div>
      <div class="messages-list" id="msg-list"><div style="padding:20px;color:var(--text-muted)">Loading...</div></div>
    `;

    try {
      const res = await Api.conversation(id, 100);
      const msgs = res.data || [];

      document.querySelector('.messages-header-phone').textContent = `${msgs.length} messages`;

      const listEl = document.getElementById('msg-list');
      if (!msgs.length) {
        listEl.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:40px">No messages yet</div>';
        return;
      }

      listEl.innerHTML = msgs.map(m => {
        const dir = m.direction || 'inbound';
        const time = m.created_at ? new Date(m.created_at).toLocaleString() : '';
        const provider = m.ai_provider_used ? `<div class="msg-provider">via ${m.ai_provider_used}</div>` : '';
        return `
          <div class="msg-bubble ${dir}">
            <div>${this._esc(m.content || '[no content]')}</div>
            ${provider}
            <div class="msg-time">${time}</div>
          </div>`;
      }).join('');

      // Scroll to bottom
      listEl.scrollTop = listEl.scrollHeight;
    } catch {
      document.getElementById('msg-list').innerHTML =
        '<div style="text-align:center;color:var(--accent-red);padding:40px">Error loading messages</div>';
    }
  },

  setupSearch() {
    const inp = document.getElementById('msg-contact-search');
    inp.addEventListener('input', () => {
      clearTimeout(this._searchTimer);
      this._searchTimer = setTimeout(() => {
        const q = inp.value.toLowerCase();
        const filtered = this.contacts.filter(c =>
          (c.name||'').toLowerCase().includes(q) ||
          c.phone_number.includes(q)
        );
        this.renderList(filtered);
      }, 200);
    });
  },

  _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },
};
