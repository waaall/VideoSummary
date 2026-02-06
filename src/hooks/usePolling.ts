/**
 * 轮询 Hook
 * 用于定时获取执行状态
 */

import { useEffect, useRef, useCallback } from 'react';
import { apiConfig } from '@/config/app';

interface UsePollingOptions<T> {
  // 轮询函数
  fetcher: () => Promise<T>;
  // 结果回调
  onData: (data: T) => void;
  // 错误回调
  onError?: (error: Error) => void;
  // 停止条件
  shouldStop?: (data: T) => boolean;
  // 轮询间隔（毫秒）
  interval?: number;
  // 是否启用
  enabled?: boolean;
}

export function usePolling<T>({
  fetcher,
  onData,
  onError,
  shouldStop,
  interval = apiConfig.pollingInterval,
  enabled = true,
}: UsePollingOptions<T>) {
  const timeoutRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const stoppedRef = useRef(false);
  const pollRef = useRef<() => Promise<void>>(async () => {});

  const poll = useCallback(async () => {
    if (!mountedRef.current || stoppedRef.current || !enabled) return;

    try {
      const data = await fetcher();

      if (!mountedRef.current) return;

      onData(data);

      // 检查是否应该停止
      if (shouldStop?.(data)) {
        stoppedRef.current = true;
        return;
      }

      // 安排下一次轮询
      timeoutRef.current = window.setTimeout(() => {
        void pollRef.current();
      }, interval);
    } catch (error) {
      if (!mountedRef.current) return;

      onError?.(error instanceof Error ? error : new Error(String(error)));

      // 发生错误时继续轮询（可能是暂时性错误）
      timeoutRef.current = window.setTimeout(() => {
        void pollRef.current();
      }, interval);
    }
  }, [fetcher, onData, onError, shouldStop, interval, enabled]);

  useEffect(() => {
    pollRef.current = poll;
  }, [poll]);

  // 启动轮询
  const start = useCallback(() => {
    stoppedRef.current = false;
    void poll();
  }, [poll]);

  // 停止轮询
  const stop = useCallback(() => {
    stoppedRef.current = true;
    if (timeoutRef.current !== null) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    if (enabled) {
      start();
    }

    return () => {
      mountedRef.current = false;
      stop();
    };
  }, [enabled, start, stop]);

  return { start, stop };
}
