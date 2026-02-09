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

/**
 * 健康检查
 */
export const checkHealth = () =>
  apiClient.get<HealthResponse>('/health');

/**
 * 创建摘要任务（缓存优先）
 */
export const createSummary = (request: SummaryCreateRequest) =>
  apiClient.post<SummaryCreateResponse>('/api/summaries', request);

/**
 * 查询任务状态
 */
export const getJobStatus = (jobId: string) =>
  apiClient.get<JobStatusResponse>(`/api/jobs/${jobId}`);

/**
 * 缓存预查
 */
export const lookupCache = (request: CacheLookupRequest) =>
  apiClient.post<CacheLookupResponse>('/api/cache/lookup', request);

/**
 * 缓存详情
 */
export const getCacheEntry = (cacheKey: string) =>
  apiClient.get<CacheEntryResponse>(`/api/cache/${cacheKey}`);

/**
 * 删除缓存
 */
export const deleteCache = (cacheKey: string) =>
  apiClient.delete<CacheDeleteResponse>(`/api/cache/${cacheKey}`);
