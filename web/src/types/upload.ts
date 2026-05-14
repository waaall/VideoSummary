/**
 * 上传相关类型
 */

export interface UploadResponse {
  file_id: string;
  original_name: string;
  size: number;
  mime_type: string;
  file_type: 'video' | 'audio' | 'subtitle';
  file_hash?: string | null;
}
