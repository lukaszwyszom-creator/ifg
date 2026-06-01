import client from './client';

const BASE = '/warehouse/items';

export const warehouseItemsApi = {
  list: (includeInactive = false) =>
    client
      .get(BASE, { params: includeInactive ? { include_inactive: true } : {} })
      .then((r) => r.data),

  getById: (id) => client.get(`${BASE}/${id}`).then((r) => r.data),

  create: (body) => client.post(BASE, body).then((r) => r.data),

  update: (id, body) => client.patch(`${BASE}/${id}`, body).then((r) => r.data),

  deactivate: (id) => client.patch(`${BASE}/${id}/deactivate`).then((r) => r.data),

  listBalance: () => client.get(`${BASE}/balance`).then((r) => r.data),
};
