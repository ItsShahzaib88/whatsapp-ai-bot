/**
 * Personalities Tab — CRUD for AI personality templates
 */

const Personalities = {
  list: [],
  editingId: null,

  async load() {
    const grid = document.getElementById('personalities-grid');
    grid.innerHTML = '<div class="loading-state">Loading personalities...</div>';
    try {
      const res = await Api.personalities();
      this.list = res.data || [];
      this.render();
    } catch {
      grid.innerHTML = '<div class="loading-state">Error loading personalities</div>';
    }
  },

  render() {
    const grid = document.getElementById('personalities-grid');
    if (!this.list.length) {
      grid.innerHTML = '<div class="loading-state">No personalities yet. Create one!</div>';
      return;
    }
    grid.innerHTML = this.list.map(p => `
      <div class="personality-card ${p.is_default ? 'is-default' : ''}">
        <div class="pc-header">
          <div class="pc-name">${this._esc(p.display_name || p.name)}</div>
          ${p.is_default ? '<span class="pc-default">Default</span>' : ''}
        </div>
        <div class="pc-meta">
          <span class="badge badge-blue">${p.tone || 'friendly'}</span>
          <span class="badge badge-gray">${p.reply_length || 'medium'}</span>
          <span class="badge badge-gray">emoji: ${p.emoji_usage || 'moderate'}</span>
          ${p.is_active ? '<span class="badge badge-green">Active</span>' : '<span class="badge badge-red">Inactive</span>'}
        </div>
        <div class="pc-instructions">${this._esc(p.persona_instructions || 'No instructions set')}</div>
        <div class="pc-actions">
          <button class="btn btn-sm btn-ghost" onclick="Personalities.openEdit('${p.id}')">Edit</button>
          ${!p.is_default ? `<button class="btn btn-sm btn-danger" onclick="Personalities.delete('${p.id}')">Delete</button>` : ''}
        </div>
      </div>
    `).join('');
  },

  _buildForm(p = {}) {
    return `
      <div class="field-group">
        <label>Name (internal, no spaces)</label>
        <input type="text" id="p-name" value="${this._esc(p.name||'')}" placeholder="e.g. friendly_bot">
      </div>
      <div class="field-group">
        <label>Display Name</label>
        <input type="text" id="p-display" value="${this._esc(p.display_name||'')}" placeholder="e.g. Friendly Assistant">
      </div>
      <div class="field-group">
        <label>Tone</label>
        <select id="p-tone" class="filter-select" style="width:100%">
          ${['friendly','professional','funny','empathetic','casual','formal'].map(t =>
            `<option value="${t}" ${p.tone===t?'selected':''}>${t}</option>`
          ).join('')}
        </select>
      </div>
      <div class="field-group">
        <label>Reply Length</label>
        <select id="p-length" class="filter-select" style="width:100%">
          ${['short','medium','long'].map(l =>
            `<option value="${l}" ${p.reply_length===l?'selected':''}>${l}</option>`
          ).join('')}
        </select>
      </div>
      <div class="field-group">
        <label>Emoji Usage</label>
        <select id="p-emoji" class="filter-select" style="width:100%">
          ${['none','minimal','moderate','heavy'].map(e =>
            `<option value="${e}" ${p.emoji_usage===e?'selected':''}>${e}</option>`
          ).join('')}
        </select>
      </div>
      <div class="field-group">
        <label>Language Style</label>
        <select id="p-lang" class="filter-select" style="width:100%">
          ${['balanced','english_only','urdu_friendly','roman_urdu','bilingual'].map(l =>
            `<option value="${l}" ${p.language_style===l?'selected':''}>${l}</option>`
          ).join('')}
        </select>
      </div>
      <div class="field-group">
        <label>Persona Instructions</label>
        <textarea id="p-instructions" rows="4">${this._esc(p.persona_instructions||'')}</textarea>
      </div>
      <div class="field-group">
        <label>Greeting Style</label>
        <input type="text" id="p-greeting" value="${this._esc(p.greeting_style||'')}" placeholder="e.g. Warm and welcoming">
      </div>
      <div class="field-group" style="flex-direction:row;align-items:center;gap:12px">
        <label style="margin:0">Set as Default</label>
        <label class="toggle">
          <input type="checkbox" id="p-default" ${p.is_default?'checked':''}>
          <span class="toggle-slider"></span>
        </label>
      </div>
    `;
  },

  openCreate() {
    this.editingId = null;
    document.getElementById('personality-modal-title').textContent = 'New Personality';
    document.getElementById('personality-modal-body').innerHTML = this._buildForm();
    document.getElementById('personality-modal').classList.remove('hidden');
    document.getElementById('personality-save-btn').onclick = () => Personalities.save();
  },

  openEdit(id) {
    const p = this.list.find(x => x.id === id);
    if (!p) return;
    this.editingId = id;
    document.getElementById('personality-modal-title').textContent = `Edit — ${p.display_name || p.name}`;
    document.getElementById('personality-modal-body').innerHTML = this._buildForm(p);
    document.getElementById('personality-modal').classList.remove('hidden');
    document.getElementById('personality-save-btn').onclick = () => Personalities.save();
  },

  async save() {
    const body = {
      name:                document.getElementById('p-name').value.trim(),
      display_name:        document.getElementById('p-display').value.trim(),
      tone:                document.getElementById('p-tone').value,
      reply_length:        document.getElementById('p-length').value,
      emoji_usage:         document.getElementById('p-emoji').value,
      language_style:      document.getElementById('p-lang').value,
      persona_instructions:document.getElementById('p-instructions').value.trim(),
      greeting_style:      document.getElementById('p-greeting').value.trim(),
      is_default:          document.getElementById('p-default').checked,
      is_active:           true,
    };
    if (!body.name || !body.display_name) {
      App.toast('Name and display name are required', 'error');
      return;
    }
    try {
      if (this.editingId) {
        await Api.updatePersonality(this.editingId, body);
        App.toast('Personality updated');
      } else {
        await Api.createPersonality(body);
        App.toast('Personality created');
      }
      this.closeModal();
      this.load();
    } catch (e) {
      App.toast(e.data?.error || 'Save failed', 'error');
    }
  },

  async delete(id) {
    if (!confirm('Delete this personality?')) return;
    try {
      await Api.deletePersonality(id);
      App.toast('Personality deleted');
      this.load();
    } catch { App.toast('Delete failed', 'error'); }
  },

  closeModal() {
    document.getElementById('personality-modal').classList.add('hidden');
    this.editingId = null;
  },

  _esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },
};
