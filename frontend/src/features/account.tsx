import { useState, type FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { deleteMe, getGenres, getMe, login, logout, register, saveGenres } from '../lib/api';

export function useProfile() { return useQuery({ queryKey: ['me'], queryFn: getMe, retry: false }); }

export function AuthPage() {
  const [mode, setMode] = useState<'login' | 'register'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const auth = useMutation({ mutationFn: () => mode === 'login' ? login(email, password) : register(email, password) });
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setNotice('');
    try {
      const result = await auth.mutateAsync();
      if (mode === 'register') { setNotice(result.message); setMode('login'); }
      else { await queryClient.invalidateQueries({ queryKey: ['me'] }); navigate('/for-you'); }
    } catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not continue'); }
  }
  return <main className="container form-page"><div className="form-card"><p className="eyebrow">Your movie space</p><h1>{mode === 'login' ? 'Welcome back' : 'Create an account'}</h1><p>Save favorites and shape your suggestions.</p>
    <form onSubmit={submit}><label>Email<input type="email" autoComplete="email" required value={email} onChange={event => setEmail(event.target.value)} /></label>
      <label>Password<input type="password" minLength={12} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required value={password} onChange={event => setPassword(event.target.value)} /></label>
      {error && <p role="alert" className="form-error">{error}</p>}{notice && <p role="status">{notice}</p>}
      <button type="submit" disabled={auth.isPending}>{auth.isPending ? 'Working…' : mode === 'login' ? 'Sign in' : 'Register'}</button></form>
    <button className="text-button" type="button" onClick={() => { setMode(mode === 'login' ? 'register' : 'login'); setError(''); }}>{mode === 'login' ? 'Need an account? Register' : 'Already registered? Sign in'}</button>
  </div></main>;
}

export function GenresPage() {
  const profile = useProfile();
  const genres = useQuery({ queryKey: ['genres'], queryFn: getGenres });
  const [selection, setSelection] = useState<string[] | null>(null);
  const [error, setError] = useState('');
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const save = useMutation({ mutationFn: saveGenres });
  if (profile.isLoading || genres.isLoading) return <main className="container form-page"><p role="status">Loading genres…</p></main>;
  if (profile.isError) return <main className="container form-page"><p><Link to="/auth">Sign in</Link> to choose genres.</p></main>;
  if (genres.isError) return <main className="container form-page"><p role="alert">Could not load genres.</p></main>;
  const chosen = selection ?? profile.data?.genres ?? [];
  async function submit(event: FormEvent) {
    event.preventDefault(); setError('');
    try { await save.mutateAsync(chosen); await queryClient.invalidateQueries({ queryKey: ['me'] }); navigate('/for-you'); }
    catch (cause) { setError(cause instanceof Error ? cause.message : 'Could not save genres'); }
  }
  return <main className="container form-page"><div className="form-card wide"><p className="eyebrow">Your taste</p><h1>Choose favorite genres</h1><p>These help shape suggestions before you have rated movies.</p><form onSubmit={submit}><div className="genre-options">{genres.data?.map(genre => <label key={genre}><input type="checkbox" checked={chosen.includes(genre)} onChange={() => setSelection(chosen.includes(genre) ? chosen.filter(item => item !== genre) : [...chosen, genre])} />{genre}</label>)}</div>{error && <p role="alert" className="form-error">{error}</p>}<button disabled={save.isPending} type="submit">Save genres</button></form></div></main>;
}

export function AccountPage() {
  const profile = useProfile();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const [error, setError] = useState('');
  async function signOut() { try { await logout(); queryClient.clear(); navigate('/'); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Sign out failed'); } }
  async function removeAccount() { if (!window.confirm('Permanently delete your account data?')) return; try { await deleteMe(); queryClient.clear(); navigate('/'); } catch (cause) { setError(cause instanceof Error ? cause.message : 'Deletion failed'); } }
  if (profile.isLoading) return <main className="container form-page"><p role="status">Loading account…</p></main>;
  if (profile.isError) return <main className="container form-page"><p><Link to="/auth">Sign in</Link> to view your account.</p></main>;
  return <main className="container form-page"><div className="form-card wide"><p className="eyebrow">Account & privacy</p><h1>Your account</h1><p>{profile.data?.email}</p><p>Selected genres: {profile.data?.genres.join(', ') || 'None yet'}</p><p><Link className="inline-link" to="/genres">Edit genres</Link></p><p>Ratings and watchlist items are stored with your account. Imported MovieLens ratings are kept separately.</p>{error && <p role="alert" className="form-error">{error}</p>}<div className="action-row"><button onClick={signOut}>Sign out</button><button className="danger" onClick={removeAccount}>Delete account</button></div></div></main>;
}
