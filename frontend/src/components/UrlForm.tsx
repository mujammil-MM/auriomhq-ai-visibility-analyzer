import clsx from 'clsx';
import { ArrowRight, Loader2, ShieldCheck } from 'lucide-react';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../lib/api';
import { isLikelyUrl, normaliseUrlInput } from '../lib/utils';

export function UrlForm({
  variant = 'hero',
  className,
  initialValue = '',
}: {
  variant?: 'hero' | 'compact';
  className?: string;
  initialValue?: string;
}) {
  const navigate = useNavigate();
  const [value, setValue] = useState(initialValue);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const url = normaliseUrlInput(value);
    if (!url) {
      setError('Enter the website you want to analyse.');
      return;
    }
    if (!isLikelyUrl(url)) {
      setError('That does not look like a valid website address. Try example.com or https://example.com.');
      return;
    }
    setBusy(true);
    try {
      const created = await api.startAudit(url);
      navigate(`/audit/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not start the audit.');
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className={clsx('w-full', className)} noValidate>
      <div
        className={clsx(
          'flex flex-col gap-2 rounded-2xl border border-lineStrong bg-surface p-2 shadow-card transition-shadow duration-300 focus-within:border-ink/40 focus-within:shadow-lift sm:flex-row sm:items-center',
          variant === 'compact' && 'rounded-xl',
        )}
      >
        <div className="flex flex-1 items-center gap-2 pl-2">
          <span className="hidden select-none font-mono text-xs text-faint sm:block">https://</span>
          <input
            value={value}
            onChange={(event) => {
              setValue(event.target.value);
              if (error) setError(null);
            }}
            placeholder="yourwebsite.com"
            aria-label="Website URL"
            inputMode="url"
            autoComplete="url"
            spellCheck={false}
            className="w-full bg-transparent py-2.5 font-mono text-[15px] text-ink outline-none placeholder:text-faint"
          />
        </div>
        <button type="submit" disabled={busy} className="btn-primary h-11 shrink-0 px-5">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {busy ? 'Starting…' : 'Analyse My Website'}
          {!busy ? <ArrowRight className="h-4 w-4" /> : null}
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1">
        <span className="inline-flex items-center gap-1.5 text-xs text-muted">
          <ShieldCheck className="h-3.5 w-3.5 text-pass" />
          Public pages only · no login · no JavaScript execution
        </span>
        <span className="text-xs text-faint">Free · real crawl · PDF report</span>
      </div>
      {error ? (
        <p className="mt-3 rounded-lg border border-fail/25 bg-failSoft px-3 py-2 text-sm text-fail">{error}</p>
      ) : null}
    </form>
  );
}
