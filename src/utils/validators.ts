/**
 * 验证工具函数
 */

import { uploadConfig } from '@/config';

/**
 * 验证 URL 格式
 */
export function isValidUrl(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol === 'http:' || parsed.protocol === 'https:';
  } catch {
    return false;
  }
}

/**
 * 验证是否为支持的视频 URL（YouTube 等）
 */
export function isSupportedVideoUrl(url: string): boolean {
  if (!isValidUrl(url)) return false;

  const supportedHosts = [
    'youtube.com',
    'www.youtube.com',
    'youtu.be',
    'm.youtube.com',
    'bilibili.com',
    'www.bilibili.com',
  ];

  try {
    const parsed = new URL(url);
    return supportedHosts.some((host) => parsed.hostname.includes(host));
  } catch {
    return false;
  }
}

/**
 * 获取文件扩展名
 */
export function getFileExtension(filename: string): string {
  const lastDot = filename.lastIndexOf('.');
  if (lastDot === -1) return '';
  return filename.slice(lastDot).toLowerCase();
}

/**
 * 验证文件类型
 */
export function isValidFileType(
  filename: string,
  acceptedFormats: string[]
): boolean {
  const ext = getFileExtension(filename);
  return acceptedFormats.includes(ext);
}

/**
 * 验证视频文件
 */
export function isValidVideoFile(filename: string): boolean {
  return isValidFileType(filename, uploadConfig.acceptedVideoFormats);
}

/**
 * 验证音频文件
 */
export function isValidAudioFile(filename: string): boolean {
  return isValidFileType(filename, uploadConfig.acceptedAudioFormats);
}

/**
 * 验证字幕文件
 */
export function isValidSubtitleFile(filename: string): boolean {
  return isValidFileType(filename, uploadConfig.acceptedSubtitleFormats);
}

/**
 * 验证文件大小
 */
export function isValidFileSize(size: number): boolean {
  return size > 0 && size <= uploadConfig.maxFileSize;
}

/**
 * 判断文件类型类别
 */
export type FileCategory = 'video' | 'audio' | 'subtitle' | 'unknown';

export function getFileCategory(filename: string): FileCategory {
  if (isValidVideoFile(filename)) return 'video';
  if (isValidAudioFile(filename)) return 'audio';
  if (isValidSubtitleFile(filename)) return 'subtitle';
  return 'unknown';
}

/**
 * 验证文件并返回错误信息
 */
export function validateFile(file: File): { valid: boolean; error?: string } {
  // 检查文件大小
  if (!isValidFileSize(file.size)) {
    const maxSizeMB = uploadConfig.maxFileSize / (1024 * 1024);
    return {
      valid: false,
      error: `文件大小超过限制（最大 ${maxSizeMB}MB）`,
    };
  }

  // 检查文件类型
  const category = getFileCategory(file.name);
  if (category === 'unknown') {
    return {
      valid: false,
      error: '不支持的文件格式',
    };
  }

  return { valid: true };
}
