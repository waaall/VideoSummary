/**
 * 执行状态查询 API
 */

import apiClient from './client';
import { apiConfig } from '@/config';
import type { PipelineRunStatusResponse } from '@/types/pipeline';

/**
 * 查询运行状态
 * @param runId 运行 ID
 */
export const getRunStatus = (runId: string) =>
  apiClient.get<PipelineRunStatusResponse>(`/pipeline/run/${runId}`);

/**
 * SSE 实时订阅运行事件
 * @param runId 运行 ID
 * @param onMessage 消息回调
 * @returns 取消订阅函数
 */
export const subscribeRunEvents = (
  runId: string,
  onMessage: (payload: PipelineRunStatusResponse) => void
): (() => void) => {
  const url = `${apiConfig.baseUrl}/pipeline/run/${runId}/events`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as PipelineRunStatusResponse;
      onMessage(data);
    } catch (error) {
      console.error('解析 SSE 消息失败:', error);
    }
  };

  eventSource.onerror = (error) => {
    console.error('SSE 连接错误:', error);
    eventSource.close();
  };

  // 返回取消订阅函数
  return () => eventSource.close();
};
