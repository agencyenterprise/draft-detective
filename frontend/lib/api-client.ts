import { client } from '@/lib/generated-api/client.gen';
import { baseUrl } from '@/lib/api';
import { ApiError } from '@/lib/api-error';

/**
 * Configures the generated API client (host, token, error mapping) when this module loads, before any component renders,
 * so a request made from a first render or effect already reaches the backend host.
 * `ApiConfig` keeps the token current; it is read per request, so a refreshed session needs
 * no reconfiguration.
 */
let accessToken: string | undefined;

client.setConfig({ baseUrl });

client.interceptors.request.use((request) => {
  if (accessToken && !request.headers.has('Authorization')) {
    request.headers.set('Authorization', `Bearer ${accessToken}`);
  }
  return request;
});

client.interceptors.error.use((error, response) => {
  if (response instanceof Response) {
    // A request-validation 422 sends `detail` as a list of objects, which is no reason to show.
    const detail: unknown = (error as { detail?: unknown })?.detail;
    return new ApiError(response.status, typeof detail === 'string' ? detail : undefined);
  }
  return error as Error;
});

/** Sets the bearer token every client request carries. Ignored on the server, where the module is shared between users. */
export function setApiAccessToken(token: string | undefined): void {
  if (typeof window === 'undefined') return;
  accessToken = token;
}
