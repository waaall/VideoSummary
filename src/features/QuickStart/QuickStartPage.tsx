/**
 * 快速开始页面
 * 提供 URL 和本地文件两种处理入口
 */

import { useState, useCallback } from 'react';
import { Tabs, message } from 'antd';
import { LinkOutlined, UploadOutlined } from '@ant-design/icons';
import { UrlInput } from './UrlInput';
import { LocalUpload } from './LocalUpload';
import { ResultDisplay } from './ResultDisplay';
import { useSummaryJob } from '@/hooks';
import styles from './QuickStartPage.module.css';

type TabKey = 'url' | 'local';

export function QuickStartPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('url');
  const [submitting, setSubmitting] = useState(false);

  const {
    status,
    jobId,
    summaryText,
    cacheStatus,
    cacheKey,
    error,
    isRunning,
    submitSummary,
    reset,
  } = useSummaryJob({
    onComplete: () => {
      message.success('处理完成');
      setSubmitting(false);
    },
    onError: (err) => {
      message.error(`处理失败: ${err}`);
      setSubmitting(false);
    },
  });

  const handleUrlSubmit = useCallback(
    async (url: string, refresh: boolean) => {
      setSubmitting(true);
      reset();

      try {
        await submitSummary(
          {
            source_type: 'url',
            source_url: url,
            refresh,
          },
          { sourceUrl: url }
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
        setSubmitting(false);
      }
    },
    [reset, submitSummary]
  );

  const handleLocalSubmit = useCallback(
    async (fileId: string, refresh: boolean, fileName?: string) => {
      setSubmitting(true);
      reset();

      try {
        await submitSummary(
          {
            source_type: 'local',
            file_id: fileId,
            refresh,
          },
          { fileName }
        );
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
        setSubmitting(false);
      }
    },
    [reset, submitSummary]
  );

  const tabItems = [
    {
      key: 'url',
      label: (
        <span className={styles.tabLabel}>
          <LinkOutlined />
          URL 处理
        </span>
      ),
      children: (
        <UrlInput
          onSubmit={handleUrlSubmit}
          loading={submitting || isRunning}
        />
      ),
    },
    {
      key: 'local',
      label: (
        <span className={styles.tabLabel}>
          <UploadOutlined />
          本地文件
        </span>
      ),
      children: (
        <LocalUpload
          onSubmit={handleLocalSubmit}
          loading={submitting || isRunning}
        />
      ),
    },
  ];

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>视频摘要</h1>
        <p className={styles.description}>
          输入视频 URL 或上传本地文件，自动生成智能摘要
        </p>
      </div>

      <div className={styles.inputSection}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as TabKey)}
          items={tabItems}
          className={styles.tabs}
        />
      </div>

      <ResultDisplay
        status={status}
        jobId={jobId}
        summaryText={summaryText}
        cacheStatus={cacheStatus}
        cacheKey={cacheKey}
        error={error}
        onReset={reset}
      />
    </div>
  );
}
