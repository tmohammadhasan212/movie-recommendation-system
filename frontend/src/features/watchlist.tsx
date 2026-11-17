import { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MoviePoster } from '../components/MoviePoster';
import { getGenres, getWatchlistMovies, removeWatchlist, type WatchlistSort } from '../lib/api';
import { useProfile } from './account';

const sortOptions: { value: WatchlistSort; label: string }[] = [
  { value: 'recent', label: 'Recently added' },
  { value: 'title', label: 'Title' },
  { value: 'year_desc', label: 'Newest release' },
  { value: 'rating_desc', label: 'Highest rated' },
];

export function WatchlistPage() {
  const profile = useProfile();
  const [genre, setGenre] = useState('');
  const [sort, setSort] = useState<WatchlistSort>('recent');
  const [page, setPage] = useState(1);
  const genres = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  const watchlist = useQuery({
    queryKey: ['watchlist-movies', genre, sort, page],
    queryFn: () => getWatchlistMovies(genre, sort, page),
    enabled: Boolean(profile.data),
  });
  const queryClient = useQueryClient();
  const remove = useMutation({
    mutationFn: removeWatchlist,
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['watchlist'] }),
        queryClient.invalidateQueries({ queryKey: ['watchlist-movies'] }),
        queryClient.invalidateQueries({ queryKey: ['recommendations'] }),
      ]);
    },
  });

  if (profile.isLoading) return <main className="container watchlist-page"><p role="status">Loading your watchlist…</p></main>;
  if (profile.isError) return <main className="container watchlist-page"><div className="empty"><h1>Your watchlist</h1><p><Link className="inline-link" to="/auth">Sign in</Link> to save movies for later.</p></div></main>;

  const totalPages = watchlist.data ? Math.max(1, Math.ceil(watchlist.data.total / watchlist.data.limit)) : 1;
  return <main className="container watchlist-page">
    <div className="watchlist-heading"><div><p className="eyebrow">Saved for later</p><h1>Your watchlist</h1><p>Keep the movies you want to watch in one place.</p></div>
      <div className="watchlist-filters"><label>Genre<select value={genre} onChange={event => { setGenre(event.target.value); setPage(1); }}><option value="">All genres</option>{genres.data?.map(item => <option key={item} value={item}>{item}</option>)}</select></label><label>Sort by<select value={sort} onChange={event => { setSort(event.target.value as WatchlistSort); setPage(1); }}>{sortOptions.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}</select></label></div>
    </div>
    {watchlist.isLoading && <p role="status">Loading saved movies…</p>}
    {watchlist.isError && <p role="alert">Could not load your watchlist: {watchlist.error.message}</p>}
    {remove.isError && <p role="alert">Could not remove that movie: {remove.error.message}</p>}
    {watchlist.data?.total === 0 && !genre && <div className="empty watchlist-empty"><h2>Your list is ready for its first movie</h2><p>Explore the catalog and choose “Add to watchlist” on any movie.</p><Link className="watchlist-cta" to="/">Discover movies</Link></div>}
    {watchlist.data?.total === 0 && genre && <div className="empty"><h2>No saved movies in this genre</h2><p>Choose another genre or show your entire watchlist.</p></div>}
    <div className="watchlist-grid">{watchlist.data?.items.map(item => { const rating = item.movie.ratings?.[0]; return <article className="watchlist-card" key={item.movie.id}><Link to={`/movies/${item.movie.id}`}><MoviePoster movie={item.movie} /><div><h2>{item.movie.title}</h2><p>{item.movie.release_year ?? 'Year unknown'}{rating ? ` · ${rating.source} ${rating.score.toFixed(1)}` : ''}</p><div className="chips">{item.movie.genres.slice(0, 2).map(value => <span key={value}>{value}</span>)}</div></div></Link><button type="button" disabled={remove.isPending && remove.variables === item.movie.id} onClick={() => remove.mutate(item.movie.id)} aria-label={`Remove ${item.movie.title} from watchlist`}>Remove</button></article>; })}</div>
    {watchlist.data && watchlist.data.total > watchlist.data.limit && <nav className="pagination" aria-label="Watchlist pages"><button disabled={page === 1} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page} of {totalPages}</span><button disabled={page >= totalPages} onClick={() => setPage(value => value + 1)}>Next</button></nav>}
  </main>;
}
