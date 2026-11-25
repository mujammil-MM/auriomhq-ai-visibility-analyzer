import type {
  AuditStatus, Methodology, PublicConfig, Report, ShareResult,
} from './types';

const JSON_HEADERS = { 'Content-Type': 'application/json' };

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, init);
  } catch {
    throw new ApiError('Network error — could not reach the analyser. Please check your connection.', 0);
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = await response.json();
      if (typeof body?.detail === 'string') {
        detail = body.detail;
      } else if (Array.isArray(body?.detail) && body.detail[0]?.msg) {
        detail = body.detail[0].msg;
      }
    } catch {
      /* keep generic message */
    }
    throw new ApiError(detail, response.status);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** Local/docker POST returns a job stub; on serverless the POST returns the finished audit. */
export type AuditStartResponse = Pick<AuditStatus, 'id' | 'status' | 'url'> &
  Partial<AuditStatus> & { pollUrl?: string };

export const api = {
  config: () => request<PublicConfig>('/api/config'),
  methodology: () => request<Methodology>('/api/methodology'),
  startAudit: (url: string, maxPages?: number) =>
    request<AuditStartResponse>('/api/audits', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ url, max_pages: maxPages ?? null }),
    }),
  getAudit: (id: string) => request<AuditStatus>(`/api/audits/${id}`),
  shareAudit: (id: string, visibility: 'public' | 'private') =>
    request<ShareResult>(`/api/audits/${id}/share`, {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify({ visibility }),
    }),
  unshareAudit: (id: string) =>
    request<{ visibility: string }>(`/api/audits/${id}/share`, { method: 'DELETE' }),
  getSharedReport: (token: string) =>
    request<Report & { shared: boolean; createdAt?: string }>(`/api/reports/${token}`),
  pdfUrl: (id: string) => `/api/audits/${id}/pdf`,
  sharedPdfUrl: (token: string) => `/api/reports/${token}/pdf`,
  submitLead: (payload: {
    name: string;
    email: string;
    business: string;
    website: string;
    interest: string;
    message: string;
    audit_id: string;
    source: string;
    company_website_confirm: string;
  }) =>
    request<{ ok: boolean; id: string | null; message: string; delivered: string[] }>('/api/leads', {
      method: 'POST',
      headers: JSON_HEADERS,
      body: JSON.stringify(payload),
    }),
};
