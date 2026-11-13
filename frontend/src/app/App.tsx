import { useState, type FormEvent } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link, NavLink, Route, Routes, useParams } from 'react-router-dom';
import { getGenres, getMovie, getMovies, type Movie } from '../lib/api';

const posterColors = ['#7d526a', '#546f75', '#9b674d', '#5e647a', '#817b4f'];

function MovieCard({ movie }: { movie: Movie }) {
  return <article className="movie-card">
    <Link to={`/movies/${movie.id}`} aria-label={`View ${movie.title}`}>
      <div className="poster" style={{ background: posterColors[movie.id % posterColors.length] }} aria-hidden="true">
        <span>{movie.title.slice(0, 1).toUpperCase()}</span>
      </div>
      <div className="card-copy"><h3>{movie.title}</h3><p>{movie.release_year ?? 'Year unknown'}</p>
        <div className="chips">{movie.genres.slice(0, 2).map(genre => <span key={genre}>{genre}</span>)}</div>
      </div>
    </Link>
  </article>;
}

function Discovery() {
  const [draft, setDraft] = useState('');
  const [query, setQuery] = useState('');
  const [genre, setGenre] = useState('');
  const [page, setPage] = useState(1);
  const movies = useQuery({ queryKey: ['movies', query, genre, page], queryFn: () => getMovies(query, genre, page) });
  const genres = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  function search(event: FormEvent) { event.preventDefault(); setPage(1); setQuery(draft.trim()); }
  return <>
    <section className="hero"><p className="eyebrow">Explore the catalog</p><h1>Find your next <em>movie night.</em></h1>
      <p>Browse real MovieLens titles. Personalized suggestions are coming as the project grows.</p>
      <form className="search" onSubmit={search}><label className="sr-only" htmlFor="movie-search">Search movie titles</label>
        <input id="movie-search" value={draft} onChange={event => setDraft(event.target.value)} maxLength={100} placeholder="Search by title" />
        <button type="submit">Search</button></form>
    </section>
    <main className="container"><div className="section-heading"><div><p className="eyebrow">The collection</p><h2>Discover movies</h2></div>
      <label className="filter">Genre <select value={genre} onChange={event => { setGenre(event.target.value); setPage(1); }}>
        <option value="">All genres</option>{genres.data?.map(item => <option key={item} value={item}>{item}</option>)}</select></label></div>
      {movies.isLoading && <p role="status">Loading movies…</p>}
      {movies.isError && <p role="alert">Could not load the catalog: {movies.error.message}</p>}
      {movies.data && !movies.data.catalog_seeded && <div className="empty"><h3>Catalog not seeded yet</h3><p>Run <code>make data-download</code> and <code>make data-import</code> to load MovieLens titles.</p></div>}
      {movies.data?.catalog_seeded && movies.data.items.length === 0 && <div className="empty"><h3>No matches</h3><p>Try another title or genre.</p></div>}
      {movies.data && <><div className="movie-grid">{movies.data.items.map(movie => <MovieCard key={movie.id} movie={movie} />)}</div>
        {movies.data.total > movies.data.limit && <nav className="pagination" aria-label="Movie pages"><button disabled={page === 1} onClick={() => setPage(page - 1)}>Previous</button><span>Page {page} of {Math.ceil(movies.data.total / movies.data.limit)}</span><button disabled={page * movies.data.limit >= movies.data.total} onClick={() => setPage(page + 1)}>Next</button></nav>}</>}
    </main>
  </>;
}

function Detail() {
  const { id } = useParams();
  const movie = useQuery({ queryKey: ['movie', id], queryFn: () => getMovie(Number(id)), enabled: !!id });
  return <main className="container detail"><Link className="back" to="/">← Back to discovery</Link>
    {movie.isLoading && <p role="status">Loading movie…</p>}
    {movie.isError && <p role="alert">Could not load this movie: {movie.error.message}</p>}
    {movie.data && <div className="detail-layout"><div className="poster large" style={{ background: posterColors[movie.data.id % posterColors.length] }} aria-hidden="true">{movie.data.title.slice(0, 1).toUpperCase()}</div><div><p className="eyebrow">{movie.data.source} catalog</p><h1>{movie.data.title}</h1><p>{movie.data.release_year ?? 'Release year unknown'}</p><div className="chips">{movie.data.genres.map(genre => <span key={genre}>{genre}</span>)}</div><p className="metadata-note">MovieLens provides titles and genres. A poster, synopsis, and cast are not available in this dataset.</p></div></div>}
  </main>;
}

function Credits() { return <main className="container prose"><p className="eyebrow">Attribution</p><h1>Credits & data</h1><p>This non-commercial demo uses the MovieLens ml-latest-small dataset from GroupLens Research at the University of Minnesota. MovieLens data has separate terms from this project's source code. GroupLens does not endorse this project.</p><p>Harper, F. M., & Konstan, J. A. (2015). The MovieLens Datasets: History and Context. ACM Transactions on Interactive Intelligent Systems, 5(4), 19:1–19:19.</p><p><a href="https://grouplens.org/datasets/movielens/latest/">Dataset information and terms</a></p></main>; }

export default function App() { return <><header className="site-header"><div className="container header-inner"><Link className="brand" to="/">recsys<span>✦</span></Link><nav aria-label="Main navigation"><NavLink to="/">Discover</NavLink><NavLink to="/credits">Credits</NavLink></nav></div></header><Routes><Route path="/" element={<Discovery />} /><Route path="/movies/:id" element={<Detail />} /><Route path="/credits" element={<Credits />} /></Routes><footer className="site-footer"><div className="container">A non-commercial MovieLens demo · <Link to="/credits">Data credits</Link></div></footer></>; }
