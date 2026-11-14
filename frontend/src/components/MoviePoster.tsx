import { useState } from 'react';
import type { Movie } from '../lib/api';

const colors = ['#7d526a', '#546f75', '#9b674d', '#5e647a', '#817b4f'];

export function MoviePoster({ movie, size = 'card' }: { movie: Movie; size?: 'card' | 'large' | 'thumb' }) {
  const [failed, setFailed] = useState(false);
  const showImage = Boolean(movie.poster_url) && !failed;
  return <div className={`poster ${size}`} style={{ background: colors[movie.id % colors.length] }}>
    {showImage
      ? <img src={movie.poster_url ?? ''} alt={`${movie.title} poster`} loading={size === 'large' ? 'eager' : 'lazy'} decoding="async" onError={() => setFailed(true)} />
      : <span aria-hidden="true">{movie.title.slice(0, 1).toUpperCase()}</span>}
  </div>;
}
