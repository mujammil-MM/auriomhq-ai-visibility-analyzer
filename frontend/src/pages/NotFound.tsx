import { Link } from 'react-router-dom';

export function NotFound() {
  return (
    <div className="mx-auto max-w-lg px-5 py-28 text-center sm:px-8">
      <p className="font-mono text-2xs uppercase tracking-[0.16em] text-faint">404</p>
      <h1 className="mt-3 text-2xl font-semibold tracking-[-0.02em]">This page does not exist</h1>
      <p className="mt-2 text-sm text-muted">
        The link may be outdated. Start from the analyser and run an audit of any public website.
      </p>
      <Link to="/" className="btn-primary mt-6">
        Back to the analyzer
      </Link>
    </div>
  );
}
