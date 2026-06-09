import { API_V1_PREFIX, getApiBaseUrl } from './config';
import { AuthError } from './auth-error';

export type ApiError = {
  code: string;
  message: string;
};

export class IfgApiClient {
  private token: string | null = null;

  setToken(token: string | null) {
    this.token = token;
  }

  getToken(): string | null {
    return this.token;
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
    const contentType = response.headers.get('content-type') ?? '';
    const cfAccess = response.headers.get('www-authenticate')?.includes('Cloudflare-Access');
    const cfRedirect =
      response.status === 302 ||
      response.status === 301 ||
      response.url.includes('cloudflareaccess.com');

    if (cfAccess || cfRedirect) {
      throw new Error(
        'API jest chronione Cloudflare Access. Użyj adresu LAN/Tailscale serwera IFG (np. http://192.168.1.50:8000).',
      );
    }

    const payload = await response.json().catch(() => null);
    if (!response.ok) {
      const message =
        (payload as { error?: ApiError })?.error?.message ??
        `HTTP ${response.status}`;
      if (response.status === 401) {
        throw new AuthError(message);
      }
      throw new Error(message);
    }

    if (payload === null && contentType.includes('text/html')) {
      throw new Error(
        'API zwróciło stronę HTML zamiast JSON — prawdopodobnie Cloudflare Access. Użyj adresu LAN serwera IFG.',
      );
    }

    return payload as T;
  }
}

export const apiClient = new IfgApiClient();
