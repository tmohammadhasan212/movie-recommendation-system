import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { MoviePoster } from '../components/MoviePoster';
import { getRecommendations } from '../lib/api';
import { useProfile } from './account';

const explanations: Record<string, string> = {
  selected_genres: 'Based on your selected genres',
  popular_in_catalog: 'Popular in this catalog',
  shared_genres: 'Shares genres with this movie',
  similar_to_high_ratings: 'Similar to movies you rated highly'
};

export function RecommendationsPage() {
  const profile = useProfile();
  const feed = useQuery({ queryKey: ['recommendations', profile.data?.profile_version], queryFn: getRecommendations });
  return <main className="container feed-page"><p className="eyebrow">Suggestions</p><h1>For your movie night</h1><p>These are suggestions based on historical MovieLens ratings and your choices, not predictions of what you will love.</p>
    {!profile.data && <p><Link className="inline-link" to="/auth">Sign in</Link> and choose genres for a more personal feed.</p>}
    {profile.data && !profile.data.genres.length && <p><Link className="inline-link" to="/genres">Choose favorite genres</Link> to shape your feed.</p>}
    {feed.isLoading && <p role="status">Finding suggestions…</p>}
    {feed.isError && <p role="alert">Could not load suggestions: {feed.error.message}</p>}
    {feed.data?.items.length === 0 && <p>No suggestions yet. The catalog may need to be imported.</p>}
    <div className="suggestions">{feed.data?.items.map(item => <article key={item.movie.id} className="suggestion"><Link to={`/movies/${item.movie.id}`}><MoviePoster movie={item.movie} size="thumb" /></Link><div><Link to={`/movies/${item.movie.id}`}><h2>{item.movie.title}</h2></Link><p>{item.movie.release_year ?? 'Year unknown'} · {item.movie.genres.join(', ') || 'Genre unknown'}</p></div><span>{explanations[item.explanation_code] ?? 'Catalog suggestion'}</span></article>)}</div>
  </main>;
}
