/**
 * 应用全局配置
 * 集中管理环境变量和常量配置
 */

// API 配置
export const apiConfig = {
  // 基础 URL，支持环境变量覆盖
  baseUrl: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8765',
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

// 前端默认设置（仅用于初始化）
export const defaultUiSettings = {
  pollingInterval: apiConfig.pollingInterval,
  requestTimeout: apiConfig.timeout,
  uploadMaxFileSizeMb: Math.round(uploadConfig.maxFileSize / (1024 * 1024)),
};

// 应用元信息
export const appMeta = {
  name: 'VideoSummary',
  version: '0.1.0',
  description: '智能视频摘要工具',
};
