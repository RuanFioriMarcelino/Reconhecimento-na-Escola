const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';
const TOKEN_KEY = 'reconhece_auth_token';

let unauthorizedHandler = null;

export function getToken() {
  return sessionStorage.getItem(TOKEN_KEY) || '';
}

export function setToken(token) {
  if (token) sessionStorage.setItem(TOKEN_KEY, token);
  else sessionStorage.removeItem(TOKEN_KEY);
}

export function clearToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function setUnauthorizedHandler(fn) {
  unauthorizedHandler = fn;
}

function toQueryString(params = {}) {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([key, val]) => {
    if (val !== undefined && val !== null && String(val).trim() !== '') {
      sp.set(key, String(val));
    }
  });
  const s = sp.toString();
  return s ? `?${s}` : '';
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const token = getToken();
  const headers = {
    ...(isFormData ? {} : { 'Content-Type': 'application/json' }),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_URL}${path}`, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && path !== '/login/') {
    clearToken();
    if (unauthorizedHandler) unauthorizedHandler();
  }

  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(data.detail || 'Não foi possível comunicar com o servidor.');
  }
  return data;
}

export const api = {
  health: () => request('/health/'),
  login: async (email, senha) => {
    const data = await request('/login/', {
      method: 'POST',
      body: JSON.stringify({ email, senha }),
    });
    if (data.token) setToken(data.token);
    return data;
  },
  logout: async () => {
    try {
      await request('/logout/', { method: 'POST' });
    } finally {
      clearToken();
    }
  },
  me: () => request('/me/'),
  bootstrap: () => request('/bootstrap/'),
  dashboard: () => request('/dashboard/'),
  live: (sinceLogId = 0, sinceAlertId = 0) =>
    request(`/live/${toQueryString({ since_log_id: sinceLogId, since_alert_id: sinceAlertId })}`),
  listPeople: (params = {}) => request(`/people/${toQueryString(params)}`),
  getPerson: (id, params = {}) => request(`/people/${id}/${toQueryString(params)}`),
  listLogs: (params = {}) => request(`/logs/${toQueryString(params)}`),
  listAlerts: (params = {}) => request(`/alerts/${toQueryString(params)}`),
  classes: () => request('/classes/'),
  classesCreate: data => request('/classes/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  createPerson: person => request('/people/', {
    method: 'POST',
    body: JSON.stringify(person),
  }),
  updatePerson: (id, person) => request(`/people/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(person),
  }),
  setPersonStatus: (id, status) => request(`/people/${id}/status/`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  }),
  enrollBiometrics: (id, files) => {
    const form = new FormData();
    const list = Array.isArray(files) ? files : [files];
    list.forEach((file, idx) => form.append('imagens', file, file.name || `quadro_${idx + 1}.jpg`));
    return request(`/people/${id}/biometrics/`, {
      method: 'POST',
      body: form,
    });
  },
  deleteBiometrics: id => request(`/people/${id}/biometrics/`, { method: 'DELETE' }),
  updateAlert: (id, payload) => request(`/alerts/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  }),
  resolveAlert: id => request(`/alerts/${id}/resolve/`, {
    method: 'PATCH',
    body: JSON.stringify({ status: 'resolvido' }),
  }),
  updateSettings: data => request('/settings/', {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  createDevice: data => request('/devices/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
  updateDevice: (id, data) => request(`/devices/${id}/`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  }),
  getAuditLogs: (params = {}) => request(`/audit/${toQueryString(params)}`),
  downloadReportCsv: async (de = '', ate = '') => {
    const qs = toQueryString({ de, ate });
    const token = getToken();
    const res = await fetch(`${API_URL}/reports/export/${qs}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Falha ao exportar relatório CSV.');
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'frequencia-escolar.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  },
  registerAccess: data => request('/access/', {
    method: 'POST',
    body: JSON.stringify(data),
  }),
};
