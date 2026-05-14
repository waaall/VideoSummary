/**
 * 摘要/任务相关 API
 */

import apiClient from './client';
import type {
  SummaryCreateRequest,
  SummaryCreateResponse,
  JobStatusResponse,
  CacheLookupRequest,
  CacheLookupResponse,
  CacheEntryResponse,
  CacheDeleteResponse,
  HealthResponse,
} from '@/types/summary';
import {
  isValidCacheKey,
  isValidFileHash,
  isValidFileId,
  isValidJobId,
  isValidUrl,
} from '@/utils/validators';

function assertValidSourceRequest(request: SummaryCreateRequest | CacheLookupRequest): void {
  if (request.source_type === 'url') {
    if (!request.source_url || !isValidUrl(request.source_url)) {
      throw new Error('source_type=url 时必须提供合法的 source_url');
    }
    return;
  }

  if (request.source_type === 'local') {
    const hasFileId = typeof request.file_id === 'string' && request.file_id.length > 0;
    const hasFileHash = typeof request.file_hash === 'string' && request.file_hash.length > 0;

    if (hasFileId === hasFileHash) {
      throw new Error('source_type=local 时必须且只能提供 file_id 或 file_hash');
    }

    if (hasFileId && !isValidFileId(request.file_id!)) {
      throw new Error('file_id 格式不合法');
    }
    if (hasFileHash && !isValidFileHash(request.file_hash!)) {
      throw new Error('file_hash 格式不合法');
    }
    return;
  }

  throw new Error('source_type 仅支持 url 或 local');
}

/**
 * 健康检查
 */
export const checkHealth = () =>
  apiClient.get<HealthResponse>('/health');

/**
 * 创建摘要任务（缓存优先）
 */
export const createSummary = (request: SummaryCreateRequest) => {
  assertValidSourceRequest(request);
  return apiClient.post<SummaryCreateResponse>('/api/summaries', request);
};

/**
 * 查询任务状态
 */
export const getJobStatus = (jobId: string) => {
  if (!isValidJobId(jobId)) {
    throw new Error('job_id 格式不合法');
  }
  return apiClient.get<JobStatusResponse>(`/api/jobs/${jobId}`);
};

/**
 * 缓存预查
 */
export const lookupCache = (request: CacheLookupRequest) => {
  assertValidSourceRequest(request);
  return apiClient.post<CacheLookupResponse>('/api/cache/lookup', request);
};

/**
 * 缓存详情
 */
export const getCacheEntry = (cacheKey: string) => {
  if (!isValidCacheKey(cacheKey)) {
    throw new Error('cache_key 格式不合法');
  }
  return apiClient.get<CacheEntryResponse>(`/api/cache/${cacheKey}`);
};

/**
 * 删除缓存
 */
export const deleteCache = (cacheKey: string) => {
  if (!isValidCacheKey(cacheKey)) {
    throw new Error('cache_key 格式不合法');
  }
  return apiClient.delete<CacheDeleteResponse>(`/api/cache/${cacheKey}`);
};
