import type { Pillar, Severity, Status } from './types';

export const PILLAR_META: Record<Pillar, { label: string; name: string; blurb: string }> = {
  seo: {
    label: 'SEO',
    name: 'Search Engine Optimisation',
    blurb: 'Can search engines crawl, index and understand your pages?',
  },
  aeo: {
    label: 'AEO',
    name: 'Answer Engine Optimisation',
    blurb: 'Can an engine extract a direct, quotable answer from your content?',
  },
  geo: {
    label: 'GEO',
    name: 'Generative Engine Optimisation',
    blurb: 'Can AI systems identify your entity, read your content and trust it?',
  },
};

export const STATUS_META: Record<Status, { label: string; className: string; dot: string }> = {
  pass: { label: 'Pass', className: 'border-pass/25 bg-passSoft text-pass', dot: 'bg-pass' },
  warning: { label: 'Warning', className: 'border-warn/25 bg-warnSoft text-warn', dot: 'bg-warn' },
  fail: { label: 'Fail', className: 'border-fail/25 bg-failSoft text-fail', dot: 'bg-fail' },
  not_tested: { label: 'Not tested', className: 'border-lineStrong bg-mist text-muted', dot: 'bg-faint' },
};

export const SEVERITY_META: Record<Severity, { label: string; className: string }> = {
  critical: { label: 'Critical', className: 'text-fail' },
  high: { label: 'High', className: 'text-accent' },
  medium: { label: 'Medium', className: 'text-warn' },
  low: { label: 'Low', className: 'text-muted' },
  informational: { label: 'Info', className: 'text-faint' },
};

export function scoreColor(score: number | null | undefined): string {
  if (score === null || score === undefined) return '#8A8780';
  if (score >= 70) return '#15803D';
  if (score >= 45) return '#B45309';
  return '#B91C1C';
}

export function scoreTone(score: number | null | undefined): 'pass' | 'warn' | 'fail' | 'neutral' {
  if (score === null || score === undefined) return 'neutral';
  if (score >= 70) return 'pass';
  if (score >= 45) return 'warn';
  return 'fail';
}

export function scoreLabel(score: number | null | undefined): string {
  if (score === null || score === undefined) return 'Not scored';
  if (score >= 85) return 'Strong';
  if (score >= 70) return 'Good';
  if (score >= 55) return 'Needs work';
  if (score >= 35) return 'Weak';
  return 'Critical';
}

export function formatDate(iso?: string | null): string {
  if (!iso) return '—';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

export function formatRelative(iso?: string | null): string {
  if (!iso) return '';
  const date = new Date(iso).getTime();
  const diff = Date.now() - date;
  const minutes = Math.round(diff / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h ago`;
  return `${Math.round(hours / 24)} d ago`;
}

export function prettyUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const path = parsed.pathname === '/' ? '' : parsed.pathname;
    return `${parsed.hostname}${path}`;
  } catch {
    return url;
  }
}

export function hostOf(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '');
  } catch {
    return url;
  }
}

export function normaliseUrlInput(value: string): string {
  const trimmed = value.trim();
  if (!trimmed) return '';
  if (/^https?:\/\//i.test(trimmed)) return trimmed;
  return `https://${trimmed.replace(/^\/+/, '')}`;
}

export function isLikelyUrl(value: string): boolean {
  const candidate = normaliseUrlInput(value);
  try {
    const parsed = new URL(candidate);
    if (!['http:', 'https:'].includes(parsed.protocol)) return false;
    const host = parsed.hostname;
    if (!host || host === 'localhost') return false;
    if (/^\d+\.\d+\.\d+\.\d+$/.test(host)) return true;
    return host.includes('.') && !host.startsWith('.') && !host.endsWith('.');
  } catch {
    return false;
  }
}

export function pluralise(count: number, singular: string, plural?: string): string {
  return count === 1 ? singular : plural || `${singular}s`;
}
