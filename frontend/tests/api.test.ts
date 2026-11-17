import { afterEach, expect, test, vi } from 'vitest';
import { getMe, getMovies, getWatchlistMovies, login } from '../src/lib/api';

afterEach(() => vi.unstubAllGlobals());

function response(status: number, payload: unknown) {
  return { ok: status >= 200 && status < 300, status, json: async () => payload };
}

test('catalog client encodes filters and uses same-origin credentials', async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ items: [], page: 1, limit: 20, total: 0, catalog_seeded: false }) });
  vi.stubGlobal('fetch', fetchMock);
  await getMovies('A & B', 'Sci-Fi', 1);
  const [url, options] = fetchMock.mock.calls[0];
  expect(url).toContain('q=A+%26+B');
  expect(url).toContain('genre=Sci-Fi');
  expect(options.credentials).toBe('same-origin');
});

test('catalog client exposes API errors', async () => {
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 503, json: async () => ({ message: 'Database unavailable' }) }));
  await expect(getMovies('', '', 1)).rejects.toThrow('Database unavailable');
});

test('watchlist client sends pagination, sorting, and genre filters', async () => {
  const fetchMock = vi.fn().mockResolvedValue(response(200, { items: [], page: 2, limit: 20, total: 0 }));
  vi.stubGlobal('fetch', fetchMock);

  await getWatchlistMovies('Drama', 'rating_desc', 2);

  expect(fetchMock.mock.calls[0][0]).toBe('/api/v1/me/watchlist/movies?sort=rating_desc&page=2&limit=20&genre=Drama');
});

test('expired access is refreshed and retried with the rotated CSRF token', async () => {
  const browserDocument = { cookie: 'csrf=old-token' };
  vi.stubGlobal('document', browserDocument);
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(response(401, { message: 'Authentication required' }))
    .mockImplementationOnce(async () => {
      browserDocument.cookie = 'csrf=new-token';
      return response(200, { message: 'Session refreshed' });
    })
    .mockResolvedValueOnce(response(200, { id: '1', email: 'user@example.test', profile_version: 0, genres: [] }));
  vi.stubGlobal('fetch', fetchMock);

  await expect(getMe()).resolves.toMatchObject({ email: 'user@example.test' });

  expect(fetchMock.mock.calls.map(call => call[0])).toEqual([
    '/api/v1/me',
    '/api/v1/auth/refresh',
    '/api/v1/me'
  ]);
  expect(fetchMock.mock.calls[1][1].headers['X-CSRF-Token']).toBe('old-token');
  expect(fetchMock.mock.calls[2][1].headers['X-CSRF-Token']).toBe('new-token');
});

test('concurrent expired requests share one refresh', async () => {
  const browserDocument = { cookie: 'csrf=old-token' };
  vi.stubGlobal('document', browserDocument);
  let protectedCalls = 0;
  let refreshCalls = 0;
  let completeRefresh: (() => void) | undefined;
  const refreshGate = new Promise<void>(resolve => { completeRefresh = resolve; });
  const fetchMock = vi.fn().mockImplementation(async (url: string) => {
    if (url === '/api/v1/auth/refresh') {
      refreshCalls += 1;
      await refreshGate;
      browserDocument.cookie = 'csrf=new-token';
      return response(200, { message: 'Session refreshed' });
    }
    protectedCalls += 1;
    if (protectedCalls <= 2) return response(401, { message: 'Authentication required' });
    return response(200, { id: '1', email: 'user@example.test', profile_version: 0, genres: [] });
  });
  vi.stubGlobal('fetch', fetchMock);

  const requests = [getMe(), getMe()];
  await vi.waitFor(() => expect(refreshCalls).toBe(1));
  completeRefresh?.();
  await expect(Promise.all(requests)).resolves.toHaveLength(2);

  expect(refreshCalls).toBe(1);
  expect(protectedCalls).toBe(4);
});

test('failed refresh preserves the original authentication error', async () => {
  vi.stubGlobal('document', { cookie: 'csrf=old-token' });
  const fetchMock = vi.fn()
    .mockResolvedValueOnce(response(401, { message: 'Authentication required' }))
    .mockResolvedValueOnce(response(401, { message: 'Refresh expired' }));
  vi.stubGlobal('fetch', fetchMock);

  await expect(getMe()).rejects.toThrow('Authentication required');
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

test('login failures never trigger session refresh', async () => {
  vi.stubGlobal('document', { cookie: 'csrf=old-token' });
  const fetchMock = vi.fn().mockResolvedValue(response(401, { message: 'Invalid credentials' }));
  vi.stubGlobal('fetch', fetchMock);

  await expect(login('user@example.test', 'incorrect password')).rejects.toThrow('Invalid credentials');
  expect(fetchMock).toHaveBeenCalledTimes(1);
});
