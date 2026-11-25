import clsx from 'clsx';
import { ArrowRight, CheckCircle2, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { api } from '../lib/api';

const INTERESTS = [
  'SEO fixes',
  'AEO / answer content',
  'GEO / AI visibility',
  'Schema & entity setup',
  'Full implementation',
];

export function LeadForm({
  auditId,
  website,
  source = 'report',
  compact = false,
}: {
  auditId?: string;
  website?: string;
  source?: string;
  compact?: boolean;
}) {
  const [form, setForm] = useState({
    name: '',
    business: '',
    email: '',
    website: website ?? '',
    interest: '',
    message: '',
    honeypot: '',
  });
  const [status, setStatus] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');
  const [error, setError] = useState<string | null>(null);
  const [confirmation, setConfirmation] = useState<string>('');

  function update(key: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [key]: value }));
    if (status === 'error') {
      setStatus('idle');
      setError(null);
    }
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!form.name.trim() || !form.email.trim()) {
      setStatus('error');
      setError('Please add your name and work email so we can reply.');
      return;
    }
    setStatus('sending');
    setError(null);
    try {
      const result = await api.submitLead({
        name: form.name,
        email: form.email,
        business: form.business,
        website: form.website,
        interest: form.interest,
        message: form.message,
        audit_id: auditId ?? '',
        source,
        company_website_confirm: form.honeypot,
      });
      if (!result.ok) throw new Error('The request could not be delivered.');
      setConfirmation(result.message);
      setStatus('sent');
    } catch (err) {
      setStatus('error');
      setError(err instanceof Error ? err.message : 'Something went wrong. Please try again.');
    }
  }

  if (status === 'sent') {
    return (
      <div className="rounded-xl border border-pass/25 bg-passSoft p-6">
        <CheckCircle2 className="h-5 w-5 text-pass" />
        <p className="mt-3 text-sm font-medium text-ink">Request received</p>
        <p className="mt-1 text-[13px] leading-relaxed text-pass">{confirmation}</p>
        <p className="mt-3 text-[12px] text-muted">
          Reference: <span className="font-mono">{auditId || 'n/a'}</span>
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <input
        type="text"
        name="company_website_confirm"
        value={form.honeypot}
        onChange={(event) => update('honeypot', event.target.value)}
        tabIndex={-1}
        autoComplete="off"
        aria-hidden="true"
        className="pointer-events-none absolute h-0 w-0 opacity-0"
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Name" required>
          <input
            className="input"
            value={form.name}
            onChange={(event) => update('name', event.target.value)}
            placeholder="Your name"
            autoComplete="name"
            required
          />
        </Field>
        <Field label="Business name">
          <input
            className="input"
            value={form.business}
            onChange={(event) => update('business', event.target.value)}
            placeholder="Company"
            autoComplete="organization"
          />
        </Field>
        <Field label="Work email" required>
          <input
            className="input"
            type="email"
            value={form.email}
            onChange={(event) => update('email', event.target.value)}
            placeholder="you@company.com"
            autoComplete="email"
            required
          />
        </Field>
        <Field label="Website URL">
          <input
            className="input font-mono text-[13px]"
            value={form.website}
            onChange={(event) => update('website', event.target.value)}
            placeholder="https://example.com"
            autoComplete="url"
          />
        </Field>
      </div>

      <div>
        <p className="label mb-2">What would you like to improve?</p>
        <div className="flex flex-wrap gap-2">
          {INTERESTS.map((interest) => (
            <button
              key={interest}
              type="button"
              onClick={() => update('interest', form.interest === interest ? '' : interest)}
              className={clsx(
                'rounded-full border px-3 py-1.5 text-xs transition-colors duration-200',
                form.interest === interest
                  ? 'border-ink bg-ink text-paper'
                  : 'border-line bg-surface text-muted hover:border-lineStrong hover:text-ink',
              )}
            >
              {interest}
            </button>
          ))}
        </div>
      </div>

      {!compact ? (
        <Field label="Anything else? (optional)">
          <textarea
            className="input min-h-[92px] resize-y text-[14px]"
            value={form.message}
            onChange={(event) => update('message', event.target.value)}
            placeholder="Timelines, current challenges, pages you care about…"
          />
        </Field>
      ) : null}

      {status === 'error' && error ? (
        <p className="rounded-lg border border-fail/25 bg-failSoft px-3 py-2 text-sm text-fail">{error}</p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={status === 'sending'} className="btn-primary">
          {status === 'sending' ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          {status === 'sending' ? 'Sending…' : 'Get a Professional Audit'}
          {status !== 'sending' ? <ArrowRight className="h-4 w-4" /> : null}
        </button>
        <p className="text-[11px] leading-relaxed text-faint">
          We use your details only to reply to this request. No newsletter, no resale.
        </p>
      </div>
    </form>
  );
}

function Field({ label, required, children }: { label: string; required?: boolean; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[12.5px] font-medium text-ink">
        {label}
        {required ? <span className="ml-0.5 text-accent">*</span> : null}
      </span>
      {children}
    </label>
  );
}
