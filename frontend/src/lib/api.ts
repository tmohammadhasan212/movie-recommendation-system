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

async function request<T>(path: string): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { credentials: 'same-origin' });
  if (!response.ok) {
    const problem = await response.json().catch(() => null) as Problem | null;
    throw new Error(problem?.message ?? `Request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}

export function getMovies(query: string, genre: string, page: number): Promise<MoviePage> {
  const params = new URLSearchParams({ page: String(page), limit: '20' });
  if (query) params.set('q', query);
  if (genre) params.set('genre', genre);
  return request<MoviePage>(`/movies?${params}`);
}

export const getMovie = (id: number): Promise<Movie> => request<Movie>(`/movies/${id}`);
export const getGenres = (): Promise<string[]> => request<string[]>('/genres');
