/**
 * 应用全局配置
 * 集中管理环境变量和常量配置
 */

// API 配置
export const apiConfig = {
  // 基础 URL，支持环境变量覆盖
  baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  // 请求超时时间（毫秒）
  timeout: Number(import.meta.env.VITE_API_TIMEOUT) || 300000,
  // 轮询间隔（毫秒）
  pollingInterval: Number(import.meta.env.VITE_POLLING_INTERVAL) || 2000,
};

// 上传配置
export const uploadConfig = {
  // 最大文件大小（字节）：500MB
  maxFileSize: Number(import.meta.env.VITE_MAX_FILE_SIZE) || 500 * 1024 * 1024,
  // 允许的视频格式
  acceptedVideoFormats: ['.mp4', '.mkv', '.avi', '.mov', '.webm', '.flv'],
  // 允许的音频格式
  acceptedAudioFormats: ['.mp3', '.wav', '.m4a', '.aac', '.flac', '.ogg'],
  // 允许的字幕格式
  acceptedSubtitleFormats: ['.srt', '.ass', '.vtt', '.ssa'],
};

// 默认阈值配置
export const defaultThresholds = {
  // 字幕覆盖率最小值
  subtitleCoverageMin: 0.8,
  // 转录每分钟最小 token 数
  transcriptTokenPerMinMin: 2.0,
  // 静音检测 RMS 阈值
  audioRmsMaxForSilence: 0.01,
};

// 摘要默认配置
export const defaultSummaryOptions = {
  model: 'gpt-3.5-turbo',
  max_tokens: 500,
  prompt: undefined as string | undefined,
};

// 转录默认配置
export const defaultTranscribeConfig = {
  transcribe_model: 'faster_whisper',
  transcribe_language: 'zh',
  need_word_time_stamp: true,
};

// 应用元信息
export const appMeta = {
  name: 'VideoSummary',
  version: '0.1.0',
  description: '基于 DAG 管线系统的智能视频摘要工具',
};
