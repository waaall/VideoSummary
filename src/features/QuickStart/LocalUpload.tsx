/**
 * 本地文件上传组件
 */

import { useState, useCallback } from 'react';
import { Button, Space, Tag, Tooltip, message } from 'antd';
import {
  PlayCircleOutlined,
  FileTextOutlined,
  AudioOutlined,
  VideoCameraOutlined,
  DeleteOutlined,
} from '@ant-design/icons';
import { FileUploader } from '@/components/common';
import { uploadLocalFile } from '@/api/upload';
import type { FileCategory } from '@/utils/validators';
import styles from './LocalUpload.module.css';

interface UploadedFile {
  fileId: string;
  category: FileCategory;
  name: string;
}

interface LocalUploadProps {
  onSubmit: (files: {
    subtitle_file_id?: string;
    audio_file_id?: string;
    video_file_id?: string;
  }) => void;
  loading?: boolean;
}

// 文件类型图标
const categoryIcons: Record<FileCategory, React.ReactNode> = {
  subtitle: <FileTextOutlined />,
  audio: <AudioOutlined />,
  video: <VideoCameraOutlined />,
  unknown: null,
};

// 文件类型颜色
const categoryColors: Record<FileCategory, string> = {
  subtitle: 'cyan',
  audio: 'purple',
  video: 'blue',
  unknown: 'default',
};

// 文件类型显示名
const categoryNames: Record<FileCategory, string> = {
  subtitle: '字幕',
  audio: '音频',
  video: '视频',
  unknown: '未知',
};

export function LocalUpload({ onSubmit, loading = false }: LocalUploadProps) {
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);

  // 处理上传成功
  const handleUploadSuccess = useCallback(
    (fileId: string, category: FileCategory, originalName: string) => {
      // 检查是否已有同类型文件
      const existingIndex = uploadedFiles.findIndex((f) => f.category === category);

      if (existingIndex >= 0) {
        // 替换同类型文件
        setUploadedFiles((prev) => {
          const updated = [...prev];
          updated[existingIndex] = { fileId, category, name: originalName };
          return updated;
        });
        message.info(`已替换之前的${categoryNames[category]}文件`);
      } else {
        // 添加新文件
        setUploadedFiles((prev) => [...prev, { fileId, category, name: originalName }]);
      }
    },
    [uploadedFiles]
  );

  // 删除已上传文件
  const handleRemoveFile = useCallback((fileId: string) => {
    setUploadedFiles((prev) => prev.filter((f) => f.fileId !== fileId));
  }, []);

  // 提交处理
  const handleSubmit = useCallback(() => {
    if (uploadedFiles.length === 0) {
      message.error('请先上传文件');
      return;
    }

    const files: {
      subtitle_file_id?: string;
      audio_file_id?: string;
      video_file_id?: string;
    } = {};

    for (const file of uploadedFiles) {
      if (file.category === 'subtitle') files.subtitle_file_id = file.fileId;
      if (file.category === 'audio') files.audio_file_id = file.fileId;
      if (file.category === 'video') files.video_file_id = file.fileId;
    }

    onSubmit(files);
  }, [uploadedFiles, onSubmit]);

  // 上传函数封装
  const handleUpload = useCallback(
    async (file: File, onProgress: (percent: number) => void) => {
      const response = await uploadLocalFile(file, onProgress);
      return { file_id: response.data.file_id };
    },
    []
  );

  return (
    <div className={styles.container}>
      {/* 文件上传区 */}
      <FileUploader
        onUploadSuccess={handleUploadSuccess}
        uploadFn={handleUpload}
        disabled={loading}
        hint="可上传字幕（.srt, .ass, .vtt）、音频（.mp3, .wav）或视频文件（.mp4, .mkv）"
      />

      {/* 已上传文件列表 */}
      {uploadedFiles.length > 0 && (
        <div className={styles.fileList}>
          <div className={styles.fileListHeader}>
            <span>已上传文件</span>
            <span className={styles.fileCount}>{uploadedFiles.length} 个</span>
          </div>

          <div className={styles.files}>
            {uploadedFiles.map((file) => (
              <div key={file.fileId} className={styles.fileItem}>
                <Tag
                  icon={categoryIcons[file.category]}
                  color={categoryColors[file.category]}
                  className={styles.fileTag}
                >
                  {categoryNames[file.category]}
                </Tag>

                <span className={styles.fileName}>{file.name}</span>

                <Tooltip title="移除">
                  <Button
                    type="text"
                    size="small"
                    icon={<DeleteOutlined />}
                    onClick={() => handleRemoveFile(file.fileId)}
                    className={styles.removeButton}
                  />
                </Tooltip>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 提交按钮 */}
      <Space className={styles.actions}>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={uploadedFiles.length === 0}
        >
          开始处理
        </Button>

        {uploadedFiles.length > 0 && (
          <Button
            size="large"
            onClick={() => setUploadedFiles([])}
            disabled={loading}
          >
            清空文件
          </Button>
        )}
      </Space>

      {/* 提示信息 */}
      <p className={styles.tip}>
        <strong>提示：</strong>
        优先处理字幕文件；若无字幕则使用音频转录；若提供视频则自动提取音频。
      </p>
    </div>
  );
}
