/**
 * 摘要与任务相关类型
 */

export type SummaryStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface SummaryCreateRequest {
  source_type: 'url' | 'local';
  source_url?: string;
  file_id?: string;
  refresh?: boolean;
}

export interface SummaryCreateResponse {
  status: 'completed' | 'pending';
  cache_key: string;
  summary_text?: string | null;
  job_id?: string;
  // 客户端字段：用于标识历史记录
  history_id?: string;
  error?: string | null;
  created_at?: number;
}

export interface JobStatusResponse {
  job_id: string;
  cache_key?: string | null;
  source_name?: string | null;
  status: SummaryStatus;
  cache_status?: SummaryStatus | 'unknown' | null;
  summary_text?: string | null;
  error?: string | null;
  created_at?: number;
  updated_at?: number;
}

export interface CacheLookupRequest {
  source_type: 'url' | 'local';
  source_url?: string;
  file_id?: string;
}

export interface CacheLookupResponse {
  status: 'hit' | 'miss';
  cache_key?: string | null;
  source_name?: string | null;
}

export interface CacheEntryResponse {
  source_name?: string | null;
  summary_text?: string | null;
  [key: string]: unknown;
}

export interface CacheDeleteResponse {
  cache_key: string;
  deleted: boolean;
}

export interface HealthResponse {
  status: string;
  version: string;
}
