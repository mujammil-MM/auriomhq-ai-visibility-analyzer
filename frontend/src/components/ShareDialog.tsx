import clsx from 'clsx';
import { Globe, Loader2, Lock } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../lib/api';
import { CopyButton, Modal } from './Primitives';
import type { ShareResult } from '../lib/types';

export function ShareDialog({
  auditId,
  open,
  onClose,
  existing,
  onShared,
}: {
  auditId: string;
  open: boolean;
  onClose: () => void;
  existing?: { token: string; visibility: 'public' | 'private' } | null;
  onShared: (share: ShareResult) => void;
}) {
  const [visibility, setVisibility] = useState<'public' | 'private' | null>(
    existing?.visibility ?? null,
  );
  const [share, setShare] = useState<ShareResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setShare(null);
      setError(null);
      setVisibility(existing?.visibility ?? null);
    }
  }, [open, existing?.visibility]);

  async function create(next: 'public' | 'private') {
    setBusy(true);
    setError(null);
    try {
      const result = await api.shareAudit(auditId, next);
      setShare(result);
      onShared(result);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not create the share link.');
    } finally {
      setBusy(false);
    }
  }

  async function makePrivate() {
    setBusy(true);
    setError(null);
    try {
      await api.unshareAudit(auditId);
      setShare(null);
      onShared({ token: '', visibility: 'private', url: '', path: '' });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not change the sharing setting.');
    } finally {
      setBusy(false);
    }
  }

  const absoluteUrl =
    share?.url ??
    (existing?.token && existing.visibility === 'public'
      ? `${window.location.origin}/r/${existing.token}`
      : '');

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Share this report"
      footer={
        <button type="button" onClick={onClose} className="btn-secondary">
          Done
        </button>
      }
    >
      <p className="text-[13px] leading-relaxed text-muted">
        A share link opens a read-only version of this audit: scores, findings, recommendations and methodology.
        No account is required and no personal data is included.
      </p>

      <div className="grid gap-2 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => {
            setVisibility('public');
            void create('public');
          }}
          className={clsx(
            'rounded-xl border p-3 text-left transition-colors',
            visibility === 'public' ? 'border-ink bg-mist/60' : 'border-line hover:border-lineStrong',
          )}
        >
          <Globe className="h-4 w-4 text-ink" />
          <p className="mt-2 text-sm font-medium">Anyone with the link</p>
          <p className="mt-0.5 text-[11px] text-muted">Public, indexable-by-nobody, revocable.</p>
        </button>
        <button
          type="button"
          onClick={() => {
            setVisibility('private');
            void makePrivate();
          }}
          className={clsx(
            'rounded-xl border p-3 text-left transition-colors',
            visibility === 'private' ? 'border-ink bg-mist/60' : 'border-line hover:border-lineStrong',
          )}
        >
          <Lock className="h-4 w-4 text-ink" />
          <p className="mt-2 text-sm font-medium">Private</p>
          <p className="mt-0.5 text-[11px] text-muted">Link disabled. Only this browser session can open it.</p>
        </button>
      </div>

      {busy ? (
        <p className="inline-flex items-center gap-2 text-xs text-muted">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Updating…
        </p>
      ) : null}

      {absoluteUrl ? (
        <div className="rounded-xl border border-line bg-mist/50 p-3">
          <p className="label mb-2">Shareable link</p>
          <div className="flex items-center gap-2">
            <input
              readOnly
              value={absoluteUrl}
              onFocus={(event) => event.currentTarget.select()}
              className="w-full rounded-lg border border-line bg-surface px-3 py-2 font-mono text-[11.5px] text-ink outline-none"
            />
            <CopyButton value={absoluteUrl} label="Copy" />
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="rounded-lg border border-fail/25 bg-failSoft px-3 py-2 text-sm text-fail">{error}</p>
      ) : null}

      <p className="text-[11px] leading-relaxed text-faint">
        Share links are unguessable tokens. Revoke access at any time by switching to private. Reports are stored
        for your convenience; we do not publish them anywhere.
      </p>
    </Modal>
  );
}
