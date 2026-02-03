/**
 * 快速开始页面
 * 提供 URL 和本地文件两种处理入口
 */

import { useState, useCallback } from 'react';
import { Tabs, message } from 'antd';
import { LinkOutlined, UploadOutlined } from '@ant-design/icons';
import { useNavigate } from 'react-router-dom';
import { UrlInput } from './UrlInput';
import { LocalUpload } from './LocalUpload';
import { useSummaryJob } from '@/hooks';
import styles from './QuickStartPage.module.css';

type TabKey = 'url' | 'local';

export function QuickStartPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('url');
  const [submitting, setSubmitting] = useState(false);
  const navigate = useNavigate();

  const {
    submitSummary,
    reset,
  } = useSummaryJob();

  const handleUrlSubmit = useCallback(
    async (url: string, refresh: boolean) => {
      setSubmitting(true);
      reset();

      try {
        const data = await submitSummary(
          {
            source_type: 'url',
            source_url: url,
            refresh,
          },
          { sourceUrl: url }
        );

        const jobId = data.job_id;
        if (jobId) {
          const isCompleted = data.status === 'completed';
          message.success(isCompleted ? '处理完成，已进入历史任务' : '任务已提交，已进入历史任务');
          navigate(`/history/${jobId}`);
        } else {
          message.success('任务已提交，请在历史任务中查看');
          navigate('/history');
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
      } finally {
        setSubmitting(false);
      }
    },
    [reset, submitSummary, navigate]
  );

  const handleLocalSubmit = useCallback(
    async (fileId: string, refresh: boolean, fileName?: string) => {
      setSubmitting(true);
      reset();

      try {
        const data = await submitSummary(
          {
            source_type: 'local',
            file_id: fileId,
            refresh,
          },
          { fileName }
        );

        const jobId = data.job_id;
        if (jobId) {
          const isCompleted = data.status === 'completed';
          message.success(isCompleted ? '处理完成，已进入历史任务' : '任务已提交，已进入历史任务');
          navigate(`/history/${jobId}`);
        } else {
          message.success('任务已提交，请在历史任务中查看');
          navigate('/history');
        }
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
      } finally {
        setSubmitting(false);
      }
    },
    [reset, submitSummary, navigate]
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
          loading={submitting}
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
          loading={submitting}
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

    </div>
  );
}
