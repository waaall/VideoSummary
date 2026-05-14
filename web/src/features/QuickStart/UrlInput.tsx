/**
 * URL 输入组件
 */

import { useState, useCallback, useMemo } from 'react';
import { Input, Button, Collapse, Switch, Space, message } from 'antd';
import { PlayCircleOutlined, SettingOutlined, LinkOutlined } from '@ant-design/icons';
import { isValidUrl, isSupportedVideoUrl } from '@/utils/validators';
import styles from './UrlInput.module.css';

interface UrlInputProps {
  onSubmit: (url: string, refresh: boolean) => void;
  loading?: boolean;
}

export function UrlInput({ onSubmit, loading = false }: UrlInputProps) {
  const [url, setUrl] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [refresh, setRefresh] = useState(false);

  const urlStatus = useMemo(() => {
    if (!url) return { valid: false, message: '' };
    if (!isValidUrl(url)) return { valid: false, message: '请输入有效的 URL' };
    if (!isSupportedVideoUrl(url)) {
      return { valid: true, message: '此 URL 可能不受支持，但仍可尝试处理', warning: true };
    }
    return { valid: true, message: '' };
  }, [url]);

  const handleSubmit = useCallback(() => {
    if (!url || !urlStatus.valid) {
      message.error('请输入有效的视频 URL');
      return;
    }

    onSubmit(url, refresh);
  }, [url, urlStatus.valid, onSubmit, refresh]);

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
      <div className={styles.inputGroup}>
        <div className={styles.inputWrapper}>
          <LinkOutlined className={styles.inputIcon} />
          <Input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            placeholder="输入视频 URL，如 https://youtube.com/watch?v=..."
            size="large"
            className={styles.urlInput}
            onPressEnter={handleSubmit}
            status={url && !urlStatus.valid ? 'error' : undefined}
          />
        </div>

        <Button
          type="primary"
          size="large"
          icon={<PlayCircleOutlined />}
          onClick={handleSubmit}
          loading={loading}
          disabled={!url || !urlStatus.valid}
          className={styles.submitButton}
        >
          开始处理
        </Button>
      </div>

      {url && urlStatus.message && (
        <p className={`${styles.hint} ${urlStatus.warning ? styles.warning : styles.error}`}>
          {urlStatus.message}
        </p>
      )}

      <Collapse
        items={advancedItems}
        ghost
        activeKey={showAdvanced ? ['advanced'] : []}
        onChange={(keys) => setShowAdvanced(keys.includes('advanced'))}
        className={styles.advancedCollapse}
      />
    </div>
  );
}
