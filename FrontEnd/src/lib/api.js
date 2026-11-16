const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const response = await fetch(`${API_URL}${path}`, {
    headers: isFormData ? (options.headers || {}) : { 'Content-Type': 'application/json', ...(options.headers || {}) },
    credentials: 'include',
    ...options,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || 'Não foi possível comunicar com o servidor.');
  return data;
}

export const api = {
  bootstrap: () => request('/bootstrap/'),
  login: (email, senha) => request('/login/', {
    method: 'POST', body: JSON.stringify({ email, senha }),
  }),
  logout: () => request('/logout/', { method: 'POST' }),
  classes: () => request('/classes/'),
  classesCreate: data => request('/classes/', {
    method: 'POST', body: JSON.stringify(data),
  }),
  createPerson: person => request('/people/', {
    method: 'POST', body: JSON.stringify(person),
  }),
  setPersonStatus: (id, status) => request(`/people/${id}/status/`, {
    method: 'PATCH', body: JSON.stringify({ status }),
  }),
  updatePerson: (id, person) => request(`/people/${id}/`, {
    method: 'PATCH', body: JSON.stringify(person),
  }),
  enrollFace: (id, image) => {
    const form = new FormData();
    form.append('imagem', image);
    return request(`/people/${id}/face/`, {
      method: 'POST',
      headers: {},
      body: form,
    });
  },
  resolveAlert: id => request(`/alerts/${id}/resolve/`, { method: 'PATCH' }),
  registerAccess: data => request('/access/', {
    method: 'POST', body: JSON.stringify(data),
  }),
};

