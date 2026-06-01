import axios from 'axios';
import { useAuthStore } from '../store/useAuthStore';

const client = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
  timeout: 30000,
});

client.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

const LOGIN_PATH = '/ui/login';

client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !window.location.pathname.endsWith('/login')) {
      useAuthStore.getState().logout();
      window.location.replace(LOGIN_PATH);
    }
    return Promise.reject(err);
  }
);

export default client;
