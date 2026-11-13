import { afterEach, expect, test, vi } from 'vitest';
import { getMovies } from '../src/lib/api';

afterEach(() => vi.unstubAllGlobals());

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
