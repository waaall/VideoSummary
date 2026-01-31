/**
 * 执行状态管理
 */

import { create } from 'zustand';
import type { TraceEvent, ExecutionStatus, PipelineRunResponse } from '@/types/pipeline';

interface ExecutionState {
  // 执行状态
  runId: string | null;
  status: ExecutionStatus;
  lastUpdatedAt: string | null;

  // 结果
  summaryText: string | null;
  context: Record<string, unknown>;
  trace: TraceEvent[];
  error: string | null;

  // 当前执行的节点
  currentNodeId: string | null;
  completedNodes: string[];

  // Actions
  startExecution: (runId: string) => void;
  updateStatus: (status: ExecutionStatus) => void;
  updateLastUpdatedAt: (ts: string | null) => void;
  updateTrace: (trace: TraceEvent[]) => void;
  updateContext: (context: Record<string, unknown>) => void;
  setCurrentNode: (nodeId: string | null) => void;
  setNodeCompleted: (nodeId: string) => void;
  completeExecution: (result: PipelineRunResponse) => void;
  failExecution: (error: string) => void;
  reset: () => void;
}

const initialState = {
  runId: null,
  status: 'idle' as ExecutionStatus,
  lastUpdatedAt: null,
  summaryText: null,
  context: {},
  trace: [],
  error: null,
  currentNodeId: null,
  completedNodes: [],
};

export const useExecutionStore = create<ExecutionState>((set) => ({
  ...initialState,

  startExecution: (runId) =>
    set({
      runId,
      status: 'running',
      error: null,
      summaryText: null,
      context: {},
      trace: [],
      currentNodeId: null,
      completedNodes: [],
    }),

  updateStatus: (status) => set({ status }),

  updateLastUpdatedAt: (ts) => set({ lastUpdatedAt: ts }),

  updateTrace: (trace) => {
    // 从 trace 中推断当前节点和已完成节点
    const completedNodes: string[] = [];
    let currentNodeId: string | null = null;

    for (const event of trace) {
      if (event.status === 'completed' || event.status === 'skipped') {
        completedNodes.push(event.node_id);
      } else if (event.status === 'started') {
        currentNodeId = event.node_id;
      }
    }

    set({ trace, completedNodes, currentNodeId });
  },

  updateContext: (context) => set({ context }),

  setCurrentNode: (nodeId) => set({ currentNodeId: nodeId }),

  setNodeCompleted: (nodeId) =>
    set((state) => ({
      completedNodes: [...state.completedNodes, nodeId],
      currentNodeId: null,
    })),

  completeExecution: (result) =>
    set({
      status: 'completed',
      summaryText: result.summary_text || null,
      context: result.context,
      trace: result.trace,
      currentNodeId: null,
    }),

  failExecution: (error) =>
    set({
      status: 'failed',
      error,
      currentNodeId: null,
    }),

  reset: () => set(initialState),
}));

// 选择器：获取节点状态
export const getNodeStatus = (
  trace: TraceEvent[],
  nodeId: string
): TraceEvent['status'] | 'pending' => {
  const event = trace.find((e) => e.node_id === nodeId);
  return event?.status || 'pending';
};

// 选择器：计算总耗时
export const getTotalElapsedMs = (trace: TraceEvent[]): number => {
  return trace.reduce((total, event) => total + event.elapsed_ms, 0);
};
