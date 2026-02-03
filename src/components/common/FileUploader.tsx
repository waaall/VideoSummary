/**
 * 文件上传组件
 * 支持拖拽上传，带进度显示
 */

import { useState, useCallback } from 'react';
import { Upload, message, Progress } from 'antd';
import { InboxOutlined, FileOutlined, CheckCircleOutlined } from '@ant-design/icons';
import type { RcFile } from 'antd/es/upload/interface';
import { uploadConfig } from '@/config/app';
import { useSettingsStore } from '@/stores/settingsStore';
import { validateFile, getFileCategory, type FileCategory } from '@/utils/validators';
import { formatFileSize } from '@/utils/formatters';
import styles from './FileUploader.module.css';

const { Dragger } = Upload;

interface FileUploaderProps {
  // 接受的文件类型，为空则接受所有支持的类型
  accept?: FileCategory[];
  // 上传成功回调
  onUploadSuccess: (fileId: string, category: FileCategory, originalName: string) => void;
  // 上传失败回调
  onUploadError?: (error: string) => void;
  // 上传函数
  uploadFn: (file: File, onProgress: (percent: number) => void) => Promise<{ file_id: string }>;
  // 是否禁用
  disabled?: boolean;
  // 自定义提示文本
  hint?: string;
}

// 根据接受的类型生成 accept 字符串
function getAcceptString(accept?: FileCategory[]): string {
  if (!accept || accept.length === 0) {
    return [
      ...uploadConfig.acceptedVideoFormats,
      ...uploadConfig.acceptedAudioFormats,
      ...uploadConfig.acceptedSubtitleFormats,
    ].join(',');
  }

  const formats: string[] = [];
  if (accept.includes('video')) formats.push(...uploadConfig.acceptedVideoFormats);
  if (accept.includes('audio')) formats.push(...uploadConfig.acceptedAudioFormats);
  if (accept.includes('subtitle')) formats.push(...uploadConfig.acceptedSubtitleFormats);

  return formats.join(',');
}

// 获取类型描述
function getTypeDescription(accept?: FileCategory[]): string {
  if (!accept || accept.length === 0) {
    return '视频、音频或字幕文件';
  }

  const descriptions: string[] = [];
  if (accept.includes('video')) descriptions.push('视频');
  if (accept.includes('audio')) descriptions.push('音频');
  if (accept.includes('subtitle')) descriptions.push('字幕');

  return descriptions.join('、') + '文件';
}

export function FileUploader({
  accept,
  onUploadSuccess,
  onUploadError,
  uploadFn,
  disabled = false,
  hint,
}: FileUploaderProps) {
  const uploadMaxFileSizeMb = useSettingsStore((state) => state.uploadMaxFileSizeMb);
  const maxFileSizeBytes = Math.round(uploadMaxFileSizeMb * 1024 * 1024);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadStatus, setUploadStatus] = useState<'idle' | 'uploading' | 'success' | 'error'>('idle');
  const [uploadedFile, setUploadedFile] = useState<{ name: string; size: number } | null>(null);

  const acceptString = getAcceptString(accept);
  const typeDescription = getTypeDescription(accept);

  // 处理上传
  const handleUpload = useCallback(
    async (file: RcFile) => {
      // 验证文件
      const validation = validateFile(file);
      if (!validation.valid) {
        message.error(validation.error);
        onUploadError?.(validation.error!);
        return false;
      }

      // 检查文件类型是否在接受范围内
      const category = getFileCategory(file.name);
      if (accept && accept.length > 0 && !accept.includes(category)) {
        const errorMsg = `请上传${typeDescription}`;
        message.error(errorMsg);
        onUploadError?.(errorMsg);
        return false;
      }

      setUploadStatus('uploading');
      setUploadProgress(0);
      setUploadedFile({ name: file.name, size: file.size });

      try {
        const result = await uploadFn(file, (percent) => {
          setUploadProgress(percent);
        });

        setUploadStatus('success');
        setUploadProgress(100);
        onUploadSuccess(result.file_id, category, file.name);
        message.success('文件上传成功');
      } catch (error) {
        setUploadStatus('error');
        const errorMsg = error instanceof Error ? error.message : '上传失败';
        message.error(errorMsg);
        onUploadError?.(errorMsg);
      }

      return false; // 阻止 antd 默认上传行为
    },
    [accept, typeDescription, uploadFn, onUploadSuccess, onUploadError]
  );

  // 重置状态
  const handleReset = useCallback(() => {
    setUploadStatus('idle');
    setUploadProgress(0);
    setUploadedFile(null);
  }, []);

  // 渲染上传成功状态
  if (uploadStatus === 'success' && uploadedFile) {
    return (
      <div className={styles.successContainer}>
        <CheckCircleOutlined className={styles.successIcon} />
        <div className={styles.fileInfo}>
          <span className={styles.fileName}>{uploadedFile.name}</span>
          <span className={styles.fileSize}>{formatFileSize(uploadedFile.size)}</span>
        </div>
        <button className={styles.resetButton} onClick={handleReset}>
          重新上传
        </button>
      </div>
    );
  }

  // 渲染上传中状态
  if (uploadStatus === 'uploading' && uploadedFile) {
    return (
      <div className={styles.uploadingContainer}>
        <FileOutlined className={styles.fileIcon} />
        <div className={styles.uploadInfo}>
          <span className={styles.fileName}>{uploadedFile.name}</span>
          <Progress
            percent={uploadProgress}
            size="small"
            status="active"
            strokeColor="var(--color-accent-primary)"
          />
        </div>
      </div>
    );
  }

  return (
    <Dragger
      accept={acceptString}
      beforeUpload={handleUpload}
      showUploadList={false}
      disabled={disabled}
      className={styles.dragger}
    >
      <p className={styles.dragIcon}>
        <InboxOutlined />
      </p>
      <p className={styles.dragText}>点击或拖拽文件到此处上传</p>
      <p className={styles.dragHint}>
        {hint || `支持 ${typeDescription}，最大 ${formatFileSize(maxFileSizeBytes)}`}
      </p>
    </Dragger>
  );
}
