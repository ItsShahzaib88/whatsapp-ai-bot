/**
 * Auth — login, logout, token persistence
 */

const Auth = {
  TOKEN_KEY: 'wa_admin_token',
  USER_KEY:  'wa_admin_user',

  init() {
    const token = localStorage.getItem(this.TOKEN_KEY);
    const user  = localStorage.getItem(this.USER_KEY);
    if (token && user) {
      Api.token = token;
      return JSON.parse(user);
    }
    return null;
  },

  save(token, user) {
    localStorage.setItem(this.TOKEN_KEY, token);
    localStorage.setItem(this.USER_KEY, JSON.stringify(user));
    Api.token = token;
  },

  clear() {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    Api.token = null;
  },

  setupLoginForm() {
    const form   = document.getElementById('login-form');
    const errEl  = document.getElementById('login-error');
    const btnTxt = document.querySelector('#login-btn .btn-text');
    const btnLdr = document.querySelector('#login-btn .btn-loader');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      const email = document.getElementById('login-email').value.trim();
      const pass  = document.getElementById('login-password').value;

      errEl.classList.add('hidden');
      btnTxt.classList.add('hidden');
      btnLdr.classList.remove('hidden');

      try {
        const res  = await Api.login(email, pass);
        const data = res.data;
        Auth.save(data.access_token, data.user);
        App.showApp(data.user);
      } catch (err) {
        const msg = err.data?.error || 'Login failed. Check credentials.';
        errEl.textContent = msg;
        errEl.classList.remove('hidden');
      } finally {
        btnTxt.classList.remove('hidden');
        btnLdr.classList.add('hidden');
      }
    });
  },

  logout() {
    Auth.clear();
    location.reload();
  },
};
