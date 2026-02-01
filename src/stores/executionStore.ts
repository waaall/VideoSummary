/**
 * 执行状态管理
 */

import { create } from 'zustand';
import type {
  TraceEvent,
  ExecutionStatus,
  PipelineRunResponse,
} from '@/types/pipeline';

interface ExecutionState {
  // 执行状态
  runId: string | null;
  status: ExecutionStatus;
  queuedAt: number | null;
  createdAt: number | null;
  updatedAt: number | null;
  startedAt: number | null;
  endedAt: number | null;

  // 结果
  summaryText: string | null;
  context: Record<string, unknown>;
  trace: TraceEvent[];
  error: string | null;

  // 当前执行的节点
  currentNodeId: string | null;
  completedNodes: string[];

  // Actions
  startExecution: (runId: string, status?: ExecutionStatus) => void;
  updateStatus: (status: ExecutionStatus) => void;
  updateRunMeta: (meta: Partial<{
    queuedAt: number | null;
    createdAt: number | null;
    updatedAt: number | null;
    startedAt: number | null;
    endedAt: number | null;
  }>) => void;
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
  queuedAt: null,
  createdAt: null,
  updatedAt: null,
  startedAt: null,
  endedAt: null,
  summaryText: null,
  context: {},
  trace: [],
  error: null,
  currentNodeId: null,
  completedNodes: [],
};

export const useExecutionStore = create<ExecutionState>((set) => ({
  ...initialState,

  startExecution: (runId, status = 'queued') =>
    set({
      runId,
      status,
      queuedAt: null,
      createdAt: null,
      updatedAt: null,
      startedAt: null,
      endedAt: null,
      error: null,
      summaryText: null,
      context: {},
      trace: [],
      currentNodeId: null,
      completedNodes: [],
    }),

  updateStatus: (status) => set({ status }),

  updateRunMeta: (meta) =>
    set((state) => ({
      queuedAt: meta.queuedAt ?? state.queuedAt,
      createdAt: meta.createdAt ?? state.createdAt,
      updatedAt: meta.updatedAt ?? state.updatedAt,
      startedAt: meta.startedAt ?? state.startedAt,
      endedAt: meta.endedAt ?? state.endedAt,
    })),

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
      updatedAt: result.updated_at ?? null,
      startedAt: result.started_at ?? null,
      endedAt: result.ended_at ?? null,
      currentNodeId: null,
      error: null,
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
  return trace.reduce((total, event) => total + (event.elapsed_ms ?? 0), 0);
};
