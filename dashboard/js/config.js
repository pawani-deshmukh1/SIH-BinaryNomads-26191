// config.js
window.API_BASE = (
  window.location.hostname === 'localhost' ||
  window.location.hostname === '127.0.0.1'
) ? 'http://127.0.0.1:8001' : 'https://YOUR-RAILWAY-URL.railway.app';
