/**
 * 文件上传 API
 */

import apiClient from './client';
import type { UploadResponse } from '@/types/pipeline';

/**
 * 上传本地文件
 * @param file 要上传的文件
 * @param onProgress 上传进度回调 (0-100)
 */
export const uploadLocalFile = (
  file: File,
  onProgress?: (percent: number) => void
) => {
  const formData = new FormData();
  formData.append('file', file);

  return apiClient.post<UploadResponse>('/uploads', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    onUploadProgress: (progressEvent) => {
      if (onProgress && progressEvent.total) {
        const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
        onProgress(percent);
      }
    },
  });
};
