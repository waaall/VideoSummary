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
  // 前端使用 file_id，path 仅用于后端内部
  video_path?: string;
  video_file_id?: string;
  subtitle_path?: string;
  subtitle_file_id?: string;
  audio_path?: string;
  audio_file_id?: string;
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
  elapsed_ms: number;
  error?: string;
  output_keys?: string[];
}

// 执行状态
export type ExecutionStatus = 'idle' | 'running' | 'completed' | 'failed';

// 管线运行响应
export interface PipelineRunResponse {
  run_id: string;
  status: 'running' | 'completed' | 'failed';
  summary_text?: string;
  context: Record<string, unknown>;
  trace: TraceEvent[];
}

// 运行状态响应（带更新时间）
export interface PipelineRunStatusResponse extends PipelineRunResponse {
  updated_at?: string;
}

// 上传响应
export interface UploadResponse {
  file_id: string;
  original_name: string;
  size: number;
  mime_type: string;
}

// 健康检查响应
export interface HealthResponse {
  status: string;
  version: string;
}
