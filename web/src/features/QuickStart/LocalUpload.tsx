/**
 * 本地文件上传组件
 */

import { useState, useCallback } from 'react';
import { Button, Space, Tag, Tooltip, message, Collapse, Switch } from 'antd';
import {
  PlayCircleOutlined,
  FileTextOutlined,
  AudioOutlined,
  VideoCameraOutlined,
  DeleteOutlined,
  SettingOutlined,
} from '@ant-design/icons';
import { FileUploader } from '@/components/common/FileUploader';
import { uploadLocalFile } from '@/api/upload';
import type { FileCategory } from '@/utils/validators';
import styles from './LocalUpload.module.css';

interface UploadedFile {
  fileId: string;
  fileHash?: string;
  category: FileCategory;
  name: string;
}

interface LocalUploadProps {
  onSubmit: (
    fileId: string | undefined,
    fileHash: string | undefined,
    refresh: boolean,
    fileName?: string
  ) => void;
  loading?: boolean;
}

const categoryIcons: Record<FileCategory, React.ReactNode> = {
  subtitle: <FileTextOutlined />,
  audio: <AudioOutlined />,
  video: <VideoCameraOutlined />,
  unknown: null,
};

const categoryColors: Record<FileCategory, string> = {
  subtitle: 'cyan',
  audio: 'purple',
  video: 'blue',
  unknown: 'default',
};

const categoryNames: Record<FileCategory, string> = {
  subtitle: '字幕',
  audio: '音频',
  video: '视频',
  unknown: '未知',
};

export function LocalUpload({ onSubmit, loading = false }: LocalUploadProps) {
  const [uploadedFile, setUploadedFile] = useState<UploadedFile | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [refresh, setRefresh] = useState(false);

  const handleUploadSuccess = useCallback(
    (fileId: string, fileHash: string | undefined, category: FileCategory, originalName: string) => {
      setUploadedFile({ fileId, fileHash, category, name: originalName });
      message.info(`已选择${categoryNames[category]}文件`);
    },
    []
  );

  const handleRemoveFile = useCallback(() => {
    setUploadedFile(null);
  }, []);

  const handleSubmit = useCallback(() => {
    if (!uploadedFile) {
      message.error('请先上传文件');
      return;
    }

    onSubmit(uploadedFile.fileId, uploadedFile.fileHash, refresh, uploadedFile.name);
  }, [uploadedFile, onSubmit, refresh]);

  const handleUpload = useCallback(
    async (file: File, onProgress: (percent: number) => void) => {
      const response = await uploadLocalFile(file, onProgress);
      return {
        file_id: response.data.file_id,
        file_hash: response.data.file_hash ?? undefined,
      };
    },
    []
  );

  const advancedItems = [
    {
      key: 'advanced',
      label: (
        <span className={styles.advancedLabel}>
          <SettingOutlined />
          缓存策略
        </span>
      ),
      children: (
        <div className={styles.advancedForm}>
          <Space size="middle">
            <Switch checked={refresh} onChange={setRefresh} />
            <span>强制重新生成（忽略缓存）</span>
          </Space>
        </div>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      <FileUploader
        onUploadSuccess={handleUploadSuccess}
        uploadFn={handleUpload}
        disabled={loading}
        hint="可上传字幕（.srt, .ass, .vtt）、音频（.mp3, .wav）或视频文件（.mp4, .mkv）"
      />

      {uploadedFile && (
        <div className={styles.fileList}>
          <div className={styles.fileListHeader}>
            <span>已上传文件</span>
            <span className={styles.fileCount}>1 个</span>
          </div>

          <div className={styles.files}>
            <div className={styles.fileItem}>
              <Tag
                icon={categoryIcons[uploadedFile.category]}
                color={categoryColors[uploadedFile.category]}
                className={styles.fileTag}
              >
                {categoryNames[uploadedFile.category]}
              </Tag>

              <span className={styles.fileName}>{uploadedFile.name}</span>

              <Tooltip title="移除">
                <Button
                  type="text"
                  size="small"
                  icon={<DeleteOutlined />}
                  onClick={handleRemoveFile}
                  className={styles.removeButton}
                />
              </Tooltip>
            </div>
          </div>
        </div>
      )}

      <Collapse
        items={advancedItems}
        ghost
        activeKey={showAdvanced ? ['advanced'] : []}
        onChange={(keys) => setShowAdvanced(keys.includes('advanced'))}
        className={styles.advancedCollapse}
      />

      <Space className={styles.actions}>
        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={!uploadedFile}
        >
          开始处理
        </Button>

        {uploadedFile && (
          <Button
            size="large"
            onClick={handleRemoveFile}
            disabled={loading}
          >
            清空文件
          </Button>
        )}
      </Space>

      <p className={styles.tip}>
        <strong>提示：</strong>
        后端会优先使用字幕文件；若上传音频或视频，将自动进行转写后摘要。
      </p>
    </div>
  );
}
