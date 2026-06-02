import { API_V1_PREFIX, getApiBaseUrl } from './config';

export type ApiError = {
  code: string;
  message: string;
};

export class IfgApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  private url(path: string): string {
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${getApiBaseUrl()}${API_V1_PREFIX}${normalized}`;
  }

  async get<T>(path: string): Promise<T> {
    const response = await fetch(this.url(path), {
      headers: this.headers(),
    });
    return this.parse<T>(response);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    const response = await fetch(this.url(path), {
      method: 'POST',
      headers: {
        ...this.headers(),
        'Content-Type': 'application/json',
      },
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    return this.parse<T>(response);
  }

  private headers(): Record<string, string> {
    const headers: Record<string, string> = { Accept: 'application/json' };
    if (this.token) {
      headers.Authorization = `Bearer ${this.token}`;
    }
    return headers;
  }

  private async parse<T>(response: Response): Promise<T> {
    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const message =
        (payload as { error?: ApiError })?.error?.message ??
        `HTTP ${response.status}`;
      throw new Error(message);
    }
    return payload as T;
  }
}

export const apiClient = new IfgApiClient();
