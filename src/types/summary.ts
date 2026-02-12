/**
 * 摘要与任务相关类型
 */

export type SummaryStatus = 'pending' | 'running' | 'completed' | 'failed';
export type CacheStatus = SummaryStatus | 'not_found';

export interface UrlSourceRequest {
  source_type: 'url';
  source_url: string;
  file_id?: never;
  file_hash?: never;
}

export interface LocalByIdRequest {
  source_type: 'local';
  file_id: string;
  source_url?: never;
  file_hash?: never;
}

export interface LocalByHashRequest {
  source_type: 'local';
  file_hash: string;
  source_url?: never;
  file_id?: never;
}

type BaseSourceRequest = UrlSourceRequest | LocalByIdRequest | LocalByHashRequest;

export type SummaryCreateRequest = BaseSourceRequest & {
  refresh?: boolean;
};

export interface SummaryCreateResponse {
  status: SummaryStatus;
  cache_key: string;
  summary_text?: string | null;
  job_id?: string;
  source_name?: string | null;
  // 客户端字段：用于标识历史记录
  history_id?: string;
  error?: string | null;
  created_at?: number;
}

export interface JobStatusResponse {
  job_id: string;
  cache_key: string;
  source_name?: string | null;
  status: SummaryStatus;
  cache_status?: CacheStatus | null;
  summary_text?: string | null;
  error?: string | null;
  created_at?: number;
  updated_at?: number;
}

export type CacheLookupRequest = BaseSourceRequest;

export interface CacheLookupResponse {
  hit: boolean;
  status: CacheStatus;
  cache_key?: string | null;
  source_name?: string | null;
  summary_text?: string | null;
  bundle_path?: string | null;
  job_id?: string | null;
  error?: string | null;
  created_at?: number | null;
  updated_at?: number | null;
}

export interface CacheEntryResponse {
  cache_key: string;
  source_type: 'url' | 'local';
  source_ref: string;
  status: CacheStatus;
  profile_version: string;
  source_name?: string | null;
  summary_text?: string | null;
  bundle_path?: string | null;
  error?: string | null;
  created_at: number;
  updated_at: number;
  last_accessed?: number | null;
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
