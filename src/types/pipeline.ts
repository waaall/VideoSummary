/**
 * 管线相关类型定义
 */

// 节点类型枚举
export type NodeType =
  | 'InputNode'
  | 'FetchMetadataNode'
  | 'DownloadSubtitleNode'
  | 'DownloadVideoNode'
  | 'ParseSubtitleNode'
  | 'ValidateSubtitleNode'
  | 'ExtractAudioNode'
  | 'DetectSilenceNode'
  | 'TranscribeNode'
  | 'TextSummarizeNode'
  | 'WarningNode';

// 节点配置
export interface PipelineNodeConfig {
  id: string;
  type: NodeType;
  params?: Record<string, unknown>;
  // 前端扩展字段（用于可视化）
  position?: { x: number; y: number };
}

// 边配置
export interface PipelineEdgeConfig {
  id: string;
  source: string;
  target: string;
  condition?: string; // 条件表达式
}

// 管线配置
export interface PipelineConfig {
  version: string;
  entrypoint?: string;
  nodes: PipelineNodeConfig[];
  edges: PipelineEdgeConfig[];
}

// 输入参数
export interface PipelineInputs {
  source_type: 'url' | 'local';
  source_url?: string;
  video_path?: string;
  subtitle_path?: string;
  audio_path?: string;
  extra?: Record<string, unknown>;
}

// URL 自动流程输入
export interface AutoPipelineInputs {
  source_type?: 'url';
  source_url: string;
  video_path?: string;
  subtitle_path?: string;
  audio_path?: string;
  extra?: Record<string, unknown>;
}

// 本地自动流程输入
export interface LocalPipelineInputs {
  // file_id 方式（推荐）
  video_file_id?: string;
  audio_file_id?: string;
  subtitle_file_id?: string;
  // path 方式（服务端本地路径，调试用）
  video_path?: string;
  audio_path?: string;
  subtitle_path?: string;
  extra?: Record<string, unknown>;
}

// 阈值配置
export interface PipelineThresholds {
  subtitle_coverage_min: number;
  transcript_token_per_min_min: number;
  audio_rms_max_for_silence: number;
}

// 追踪事件
export interface TraceEvent {
  node_id: string;
  status: 'started' | 'completed' | 'failed' | 'skipped';
  elapsed_ms?: number;
  error?: string;
  output_keys?: string[];
  started_at?: number;
  ended_at?: number;
  retryable?: boolean;
}

// 执行状态
export type ExecutionStatus = 'idle' | 'queued' | 'running' | 'completed' | 'failed';

// 创建响应（HTTP 202）
export interface PipelineRunCreateResponse {
  run_id: string;
  status: 'queued';
  queued_at?: number;
}

// 管线运行响应
export interface PipelineRunResponse {
  run_id: string;
  status: 'queued' | 'running' | 'completed' | 'failed';
  summary_text?: string;
  context: Record<string, unknown>;
  trace: TraceEvent[];
  created_at?: number;
  updated_at?: number;
  started_at?: number;
  ended_at?: number;
  error?: string | null;
}

// 运行状态响应（带更新时间）
export type PipelineRunStatusResponse = PipelineRunResponse;

// 上传响应
export interface UploadResponse {
  file_id: string;
  original_name: string;
  size: number;
  mime_type: string;
  file_type: 'video' | 'audio' | 'subtitle';
}

// 健康检查响应
export interface HealthResponse {
  status: string;
  version: string;
}
