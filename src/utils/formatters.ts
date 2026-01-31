/**
 * 格式化工具函数
 */

/**
 * 格式化文件大小
 */
export function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B';

  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const k = 1024;
  const i = Math.floor(Math.log(bytes) / Math.log(k));

  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(2))} ${units[i]}`;
}

/**
 * 格式化持续时间（毫秒 -> 可读字符串）
 */
export function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;

  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;

  if (minutes < 60) {
    return remainingSeconds > 0 ? `${minutes}m ${remainingSeconds}s` : `${minutes}m`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  return `${hours}h ${remainingMinutes}m`;
}

/**
 * 格式化视频时长（秒 -> HH:MM:SS）
 */
export function formatVideoDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);

  if (h > 0) {
    return `${h}:${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  }

  return `${m}:${s.toString().padStart(2, '0')}`;
}

/**
 * 格式化百分比
 */
export function formatPercent(value: number, decimals = 1): string {
  return `${(value * 100).toFixed(decimals)}%`;
}

/**
 * 截断文本
 */
export function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return `${text.slice(0, maxLength - 3)}...`;
}

/**
 * 节点类型显示名称映射
 */
const nodeTypeNames: Record<string, string> = {
  InputNode: '输入',
  FetchMetadataNode: '获取元数据',
  DownloadSubtitleNode: '下载字幕',
  DownloadVideoNode: '下载视频',
  ParseSubtitleNode: '解析字幕',
  ValidateSubtitleNode: '验证字幕',
  ExtractAudioNode: '提取音频',
  DetectSilenceNode: '检测静音',
  TranscribeNode: '语音转录',
  TextSummarizeNode: '生成摘要',
  WarningNode: '警告',
};

/**
 * 获取节点类型的显示名称
 */
export function getNodeTypeName(type: string): string {
  return nodeTypeNames[type] || type;
}

/**
 * 节点状态显示名称
 */
const statusNames: Record<string, string> = {
  pending: '等待中',
  started: '执行中',
  completed: '已完成',
  failed: '失败',
  skipped: '已跳过',
};

/**
 * 获取状态的显示名称
 */
export function getStatusName(status: string): string {
  return statusNames[status] || status;
}
