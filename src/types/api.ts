/**
 * API 请求/响应类型定义
 */

import type { PipelineConfig, PipelineInputs, PipelineThresholds } from './pipeline';

// LLM 摘要选项
export interface SummaryOptions {
  model?: string;
  max_tokens?: number;
  prompt?: string;
}

// 转录配置
export interface TranscribeConfig {
  transcribe_model?: string;
  transcribe_language?: string;
  need_word_time_stamp?: boolean;
  faster_whisper_model?: string;
  faster_whisper_device?: string;
  faster_whisper_vad_filter?: boolean;
  faster_whisper_vad_threshold?: number;
}

// 管线执行选项
export interface PipelineOptions {
  work_dir?: string;
  audio_track_index?: number;
  summary?: SummaryOptions;
  transcribe_config?: TranscribeConfig;
}

// URL 自动流程请求
export interface AutoUrlRequest {
  inputs: {
    source_url: string;
  };
  options?: PipelineOptions;
  thresholds?: Partial<PipelineThresholds>;
}

// 本地自动流程请求
export interface AutoLocalRequest {
  inputs: {
    source_type: 'local';
    subtitle_file_id?: string;
    audio_file_id?: string;
    video_file_id?: string;
  };
  options?: PipelineOptions;
  thresholds?: Partial<PipelineThresholds>;
}

// 自定义管线执行请求
export interface PipelineRunRequest {
  pipeline: PipelineConfig;
  inputs: PipelineInputs;
  thresholds?: Partial<PipelineThresholds>;
  options?: PipelineOptions;
}

// API 错误响应
export interface ApiError {
  detail: string;
  status_code?: number;
}
