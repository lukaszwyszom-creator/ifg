import client from './client';

const BASE = '/warehouse-documents';

export const warehouseDocumentsApi = {
  list: (params = {}) =>
    client.get(BASE, { params }).then((r) => r.data),

  getById: (id) => client.get(`${BASE}/${id}`).then((r) => r.data),

  create: (body) => client.post(BASE, body).then((r) => r.data),

  post: (id) => client.post(`${BASE}/${id}/post`).then((r) => r.data),

  update: (id, body) => client.patch(`${BASE}/${id}`, body).then((r) => r.data),

  cancel: (id) => client.delete(`${BASE}/${id}`),
};
