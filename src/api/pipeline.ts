/**
 * 管线相关 API
 */

import apiClient from './client';
import type {
  AutoPipelineRunRequest,
  LocalPipelineRunRequest,
  PipelineRunRequest,
} from '@/types/api';
import type {
  PipelineRunCreateResponse,
  HealthResponse,
} from '@/types/pipeline';

/**
 * 健康检查
 */
export const checkHealth = () =>
  apiClient.get<HealthResponse>('/health');

/**
 * URL 自动流程
 * 优先下载字幕，失败则下载视频转录
 */
export const runAutoUrl = (request: AutoPipelineRunRequest) =>
  apiClient.post<PipelineRunCreateResponse>('/pipeline/auto/url', request);

/**
 * 本地自动流程
 * 支持本地字幕/音频/视频文件
 */
export const runAutoLocal = (request: LocalPipelineRunRequest) =>
  apiClient.post<PipelineRunCreateResponse>('/pipeline/auto/local', request);

/**
 * 自定义管线执行
 */
export const runPipeline = (request: PipelineRunRequest) =>
  apiClient.post<PipelineRunCreateResponse>('/pipeline/run', request);
