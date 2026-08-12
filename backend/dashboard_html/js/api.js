/**
 * API Client — centralised fetch wrapper
 * All API calls go through here for consistent error handling and auth.
 */

const API_BASE = '/api/v1';

const Api = {
  token: null,

  _headers() {
    const h = { 'Content-Type': 'application/json' };
    if (this.token) h['Authorization'] = `Bearer ${this.token}`;
    return h;
  },

  async request(method, path, body = null) {
    const opts = { method, headers: this._headers() };
    if (body !== null) opts.body = JSON.stringify(body);
    const res = await fetch(API_BASE + path, opts);
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) {
        Auth.logout();
      }
      throw { status: res.status, data };
    }
    return data;
  },

  get:    (path)        => Api.request('GET',    path),
  post:   (path, body)  => Api.request('POST',   path, body),
  patch:  (path, body)  => Api.request('PATCH',  path, body),
  put:    (path, body)  => Api.request('PUT',    path, body),
  delete: (path)        => Api.request('DELETE', path),

  // Auth
  login: (email, pass) => Api.post('/auth/login', { email, password: pass }),
  me:    ()            => Api.get('/auth/me'),

  // Health
  health: () => fetch('/api/v1/health').then(r => r.json()),

  // Contacts
  contacts: (page=1, limit=20, search='', ai_enabled=null) => {
    let q = `?page=${page}&limit=${limit}`;
    if (search) q += `&search=${encodeURIComponent(search)}`;
    if (ai_enabled !== null) q += `&ai_enabled=${ai_enabled}`;
    return Api.get(`/contacts${q}`);
  },
  contact:       (id)      => Api.get(`/contacts/${id}`),
  updateContact: (id, body)=> Api.patch(`/contacts/${id}`, body),
  deleteContact: (id)      => Api.delete(`/contacts/${id}`),
  updateMemory:  (id, body)=> Api.patch(`/contacts/${id}/memory`, body),
  // Dedicated toggle — no body needed, backend flips the current state
  toggleContactAI: (id)       => Api.patch(`/contacts/${id}/ai-toggle`, {}),
  setContactMode:  (id, mode) => Api.patch(`/contacts/${id}/mode`, { mode }),

  // Messages
  messages: (contact_id=null, page=1, limit=50) => {
    let q = `?page=${page}&limit=${limit}`;
    if (contact_id) q += `&contact_id=${contact_id}`;
    return Api.get(`/messages${q}`);
  },
  conversation: (contact_id, limit=50) =>
    Api.get(`/messages/conversation/${contact_id}?limit=${limit}`),

  // Personalities
  personalities:        ()          => Api.get('/personalities'),
  createPersonality:    (body)      => Api.post('/personalities', body),
  updatePersonality:    (id, body)  => Api.put(`/personalities/${id}`, body),
  deletePersonality:    (id)        => Api.delete(`/personalities/${id}`),

  // AI Settings
  aiSettings:    ()      => Api.get('/ai-settings'),
  setProvider:   (name)  => Api.patch('/ai-settings', { active_provider: name }),

  // Analytics
  stats: (days=7) => Api.get(`/analytics/stats?days=${days}`),

  // Logs
  logs: (level=null, page=1, limit=100) => {
    let q = `?page=${page}&limit=${limit}`;
    if (level) q += `&level=${level}`;
    return Api.get(`/logs${q}`);
  },
};
