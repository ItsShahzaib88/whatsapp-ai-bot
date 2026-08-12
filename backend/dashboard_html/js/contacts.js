/**
 * Contacts Tab — list, search, filter, edit, toggle AI
 */

const Contacts = {
  page: 1,
  limit: 20,
  total: 0,
  search: '',
  aiFilter: '',
  editingId: null,
  _editContact: null,

  async load() {
    const tbody = document.getElementById('contacts-tbody');
    tbody.innerHTML = `<tr><td colspan="7" class="table-loading">Loading...</td></tr>`;
    try {
      const aiEnabled = this.aiFilter === '' ? null : this.aiFilter === 'true';
      const res = await Api.contacts(this.page, this.limit, this.search, aiEnabled);
      this.total = res.pagination?.total || 0;
      this.render(res.data || []);
      this.renderPagination();
      const badge = document.getElementById('contacts-badge');
      if (badge) badge.textContent = this.total;
    } catch (e) {
      tbody.innerHTML = `<tr><td colspan="7" class="table-loading">Error loading contacts</td></tr>`;
    }
  },

  render(contacts) {
    const tbody = document.getElementById('contacts-tbody');
    if (!contacts.length) {
      tbody.innerHTML = `<tr><td colspan="7" class="table-loading">No contacts found</td></tr>`;
      return;
    }
    tbody.innerHTML = contacts.map(c => {
      const initial = (c.name || c.phone_number || '?')[0].toUpperCase();
      const lastSeen = c.last_message_at
        ? new Date(c.last_message_at).toLocaleDateString()
        : 'Never';
      const aiEnabled = c.ai_enabled !== false;  // default true
      const aiChecked = aiEnabled ? 'checked' : '';
      const aiLabel = aiEnabled
        ? '<span style="color:var(--accent-green);font-size:0.7rem;font-weight:600">ON</span>'
        : '<span style="color:var(--text-muted);font-size:0.7rem">OFF</span>';
      const modeBadge = this._modeBadge(c.auto_reply_mode, c.id);
      return `
        <tr id="contact-row-${c.id}">
          <td>
            <div class="contact-info-cell">
              <div class="contact-avatar">${initial}</div>
              <div>
                <div class="contact-name-text">${this._esc(c.name || 'Unknown')}</div>
                ${c.wa_name ? `<div class="contact-wa-name">${this._esc(c.wa_name)}</div>` : ''}
              </div>
            </div>
          </td>
          <td style="font-family:monospace;font-size:0.8rem">${this._esc(c.phone_number)}</td>
          <td>
            <div style="display:flex;align-items:center;gap:6px">
              <label class="toggle" title="Toggle AI auto-reply">
                <input type="checkbox" id="ai-toggle-${c.id}" ${aiChecked}
                  onchange="Contacts.toggleAI('${c.id}', this)">
                <span class="toggle-slider"></span>
              </label>
              <span id="ai-label-${c.id}">${aiLabel}</span>
            </div>
          </td>
          <td id="mode-cell-${c.id}">${modeBadge}</td>
          <td>
            <span style="color:var(--accent-green)">${c.total_messages_received||0}</span>
            <span style="color:var(--text-muted)"> / </span>
            <span style="color:var(--accent-blue)">${c.total_messages_sent||0}</span>
          </td>
          <td style="color:var(--text-muted);font-size:0.8rem">${lastSeen}</td>
          <td>
            <div style="display:flex;gap:6px">
              <button class="btn btn-sm btn-ghost" onclick="Contacts.openEdit('${c.id}')">Edit</button>
              <button class="btn btn-sm btn-ghost" onclick="App.viewMessages('${c.id}','${this._esc(c.name||c.phone_number)}')">Msgs</button>
            </div>
          </td>
        </tr>`;
    }).join('');
  },

  _modeBadge(mode, contactId) {
    const isAI = !mode || mode === 'ai';
    const nextMode = isAI ? 'human' : 'ai';
    const title = isAI ? 'Click to switch to Human mode' : 'Click to switch to AI mode';
    const map = {
      ai:      `<button class="badge badge-green" title="${title}" onclick="Contacts.toggleMode('${contactId}','${nextMode}')">🤖 AI Auto</button>`,
      human:   `<button class="badge badge-orange" title="${title}" onclick="Contacts.toggleMode('${contactId}','${nextMode}')">👤 Manual</button>`,
      office:  `<button class="badge badge-blue" title="${title}" onclick="Contacts.toggleMode('${contactId}','ai')">🏢 Office</button>`,
      busy:    `<button class="badge badge-gray" title="${title}" onclick="Contacts.toggleMode('${contactId}','ai')">⏳ Busy</button>`,
      night:   `<button class="badge badge-gray" title="${title}" onclick="Contacts.toggleMode('${contactId}','ai')">🌙 Night</button>`,
      vacation:`<button class="badge badge-blue" title="${title}" onclick="Contacts.toggleMode('${contactId}','ai')">✈️ Vacation</button>`,
    };
    return map[mode] || `<button class="badge badge-gray" onclick="Contacts.toggleMode('${contactId}','ai')">${mode||'AI'}</button>`;
  },

  async toggleAI(id, checkboxEl) {
    // Optimistic UI — show new state immediately, revert on error
    const newEnabled = checkboxEl.checked;
    const label = document.getElementById(`ai-label-${id}`);
    if (label) {
      label.innerHTML = newEnabled
        ? '<span style="color:var(--accent-green);font-size:0.7rem;font-weight:600">ON</span>'
        : '<span style="color:var(--text-muted);font-size:0.7rem">OFF</span>';
    }
    checkboxEl.disabled = true;
    try {
      const res = await Api.toggleContactAI(id);
      App.toast(res.message || `AI ${newEnabled ? 'enabled ✅' : 'disabled ❌'}`);
    } catch (e) {
      // Revert on failure
      checkboxEl.checked = !newEnabled;
      if (label) {
        label.innerHTML = !newEnabled
          ? '<span style="color:var(--accent-green);font-size:0.7rem;font-weight:600">ON</span>'
          : '<span style="color:var(--text-muted);font-size:0.7rem">OFF</span>';
      }
      App.toast('Failed to update AI toggle', 'error');
    } finally {
      checkboxEl.disabled = false;
    }
  },

  async toggleMode(id, newMode) {
    const modeCell = document.getElementById(`mode-cell-${id}`);
    try {
      const res = await Api.setContactMode(id, newMode);
      App.toast(res.message || `Mode set to ${newMode.toUpperCase()}`);
      // Update badge in-place without full reload
      if (modeCell) modeCell.innerHTML = this._modeBadge(newMode, id);
    } catch {
      App.toast('Failed to update mode', 'error');
    }
  },

  async openEdit(id) {
    try {
      const res = await Api.contact(id);
      const c = res.data.contact;
      this.editingId = id;
      this._editContact = c;
      document.getElementById('contact-modal-title').textContent = `Edit — ${c.name || c.phone_number}`;
      document.getElementById('contact-modal-body').innerHTML = `
        <div class="field-group">
          <label>Name</label>
          <input type="text" id="edit-name" value="${this._esc(c.name||'')}">
        </div>
        <div class="field-group">
          <label>Nickname</label>
          <input type="text" id="edit-nickname" value="${this._esc(c.nickname||'')}">
        </div>
        <div class="field-group">
          <label>Relationship</label>
          <select id="edit-relationship" class="filter-select" style="width:100%">
            ${['family','friend','colleague','client','romantic','unknown'].map(r =>
              `<option value="${r}" ${c.relationship===r?'selected':''}>${r}</option>`
            ).join('')}
          </select>
        </div>
        <div class="field-group">
          <label>Auto Reply Mode</label>
          <select id="edit-mode" class="filter-select" style="width:100%">
            ${['ai','human','office','busy','night','vacation'].map(m =>
              `<option value="${m}" ${c.auto_reply_mode===m?'selected':''}>${m}</option>`
            ).join('')}
          </select>
        </div>
        <div class="field-group">
          <label>Preferred Language</label>
          <select id="edit-lang" class="filter-select" style="width:100%">
            ${[['en','English'],['ur','Urdu'],['roman_urdu','Roman Urdu'],['auto','Auto Detect']].map(([v,l]) =>
              `<option value="${v}" ${c.preferred_language===v?'selected':''}>${l}</option>`
            ).join('')}
          </select>
        </div>
        <div class="field-group">
          <label>Notes</label>
          <textarea id="edit-notes" rows="3">${this._esc(c.notes||'')}</textarea>
        </div>
      `;
      document.getElementById('contact-modal').classList.remove('hidden');
      document.getElementById('contact-save-btn').onclick = () => Contacts.saveEdit();
    } catch { App.toast('Failed to load contact', 'error'); }
  },

  async saveEdit() {
    const body = {
      name:             document.getElementById('edit-name').value.trim(),
      nickname:         document.getElementById('edit-nickname').value.trim(),
      relationship:     document.getElementById('edit-relationship').value,
      auto_reply_mode:  document.getElementById('edit-mode').value,
      preferred_language: document.getElementById('edit-lang').value,
      notes:            document.getElementById('edit-notes').value.trim(),
    };
    try {
      await Api.updateContact(this.editingId, body);
      App.toast('Contact updated');
      this.closeModal();
      this.load();
    } catch { App.toast('Update failed', 'error'); }
  },

  closeModal() {
    document.getElementById('contact-modal').classList.add('hidden');
    this.editingId = null;
  },

  setupSearch() {
    const inp = document.getElementById('contacts-search');
    let timer;
    inp.addEventListener('input', () => {
      clearTimeout(timer);
      timer = setTimeout(() => {
        this.search = inp.value.trim();
        this.page = 1;
        this.load();
      }, 350);
    });

    document.getElementById('contacts-filter').addEventListener('change', (e) => {
      this.aiFilter = e.target.value;
      this.page = 1;
      this.load();
    });
  },

  renderPagination() {
    const el = document.getElementById('contacts-pagination');
    const totalPages = Math.ceil(this.total / this.limit);
    if (totalPages <= 1) { el.innerHTML = ''; return; }
    let html = `<button class="page-btn" onclick="Contacts.goPage(${this.page-1})" ${this.page<=1?'disabled':''}>&#8249;</button>`;
    for (let i = Math.max(1, this.page-2); i <= Math.min(totalPages, this.page+2); i++) {
      html += `<button class="page-btn ${i===this.page?'active':''}" onclick="Contacts.goPage(${i})">${i}</button>`;
    }
    html += `<button class="page-btn" onclick="Contacts.goPage(${this.page+1})" ${this.page>=totalPages?'disabled':''}>&#8250;</button>`;
    el.innerHTML = html;
  },

  goPage(p) {
    if (p < 1) return;
    this.page = p;
    this.load();
  },

  _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },
};
