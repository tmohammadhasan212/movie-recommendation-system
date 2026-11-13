export interface Movie {
  id: number;
  title: string;
  release_year: number | null;
  genres: string[];
  source: string;
}

export interface MoviePage {
  items: Movie[];
  page: number;
  limit: number;
  total: number;
  catalog_seeded: boolean;
}

interface Problem {
  code: string;
  message: string;
  request_id: string;
}

async function request<T>(path: string, method = 'GET', body?: unknown, idempotencyKey?: string): Promise<T> {
  const csrf = typeof document === 'undefined' ? undefined : document.cookie.split('; ').find(part => part.startsWith('csrf='))?.split('=')[1];
  const response = await fetch(`/api/v1${path}`, {
    method,
    credentials: 'same-origin',
    headers: {
      ...(body === undefined ? {} : { 'Content-Type': 'application/json' }),
      ...(csrf ? { 'X-CSRF-Token': decodeURIComponent(csrf) } : {}),
      ...(idempotencyKey ? { 'Idempotency-Key': idempotencyKey } : {})
    },
    ...(body === undefined ? {} : { body: JSON.stringify(body) })
  });
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as Problem | null;
    throw new Error(problem?.message ?? `Request failed (${response.status})`);
  }
  return response.status === 204 ? (undefined as T) : response.json() as Promise<T>;
}

export function getMovies(query: string, genre: string, page: number): Promise<MoviePage> {
  const params = new URLSearchParams({ page: String(page), limit: '20' });
  if (query) params.set('q', query);
  if (genre) params.set('genre', genre);
  return request<MoviePage>(`/movies?${params}`);
}

export const getMovie = (id: number): Promise<Movie> => request<Movie>(`/movies/${id}`);
export const getGenres = (): Promise<string[]> => request<string[]>('/genres');

export interface Profile { id: string; email: string; profile_version: number; genres: string[] }
export interface Recommendation { movie: Movie; source: string; explanation_code: string }
export interface RecommendationFeed { items: Recommendation[]; model_version: string | null; fallback_reason: string }
export interface Rating { movie_id: number; rating: number }

export const register = (email: string, password: string): Promise<{ message: string }> => request('/auth/register', 'POST', { email, password });
export const login = (email: string, password: string): Promise<{ message: string }> => request('/auth/login', 'POST', { email, password });
export const logout = (): Promise<{ message: string }> => request('/auth/logout', 'POST');
export const getMe = (): Promise<Profile> => request('/me');
export const deleteMe = (): Promise<void> => request('/me', 'DELETE');
export const saveGenres = (genres: string[]): Promise<{ genres: string[]; profile_version: number }> => request('/me/genres', 'PUT', { genres });
export const getRatings = (): Promise<Rating[]> => request('/me/ratings');
export const setRating = (movieId: number, rating: number): Promise<Rating> => request(`/me/ratings/${movieId}`, 'PUT', { rating }, crypto.randomUUID());
export const removeRating = (movieId: number): Promise<void> => request(`/me/ratings/${movieId}`, 'DELETE');
export const getWatchlist = (): Promise<number[]> => request('/me/watchlist');
export const addWatchlist = (movieId: number): Promise<void> => request(`/me/watchlist/${movieId}`, 'PUT');
export const removeWatchlist = (movieId: number): Promise<void> => request(`/me/watchlist/${movieId}`, 'DELETE');
export const getRecommendations = (): Promise<RecommendationFeed> => request('/recommendations');
export const getSimilar = (movieId: number): Promise<RecommendationFeed> => request(`/movies/${movieId}/similar?limit=6`);
