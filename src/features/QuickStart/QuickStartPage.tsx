/**
 * 快速开始页面
 * 提供 URL 和本地文件两种自动处理流程入口
 */

import { useState, useCallback } from 'react';
import { Tabs, message } from 'antd';
import { LinkOutlined, UploadOutlined } from '@ant-design/icons';
import { UrlInput } from './UrlInput';
import { LocalUpload } from './LocalUpload';
import { ResultDisplay } from './ResultDisplay';
import { runAutoUrl, runAutoLocal } from '@/api/pipeline';
import { usePipelineExecution } from '@/hooks';
import { useSettingsStore } from '@/stores';
import type { PipelineOptions } from '@/types/api';
import styles from './QuickStartPage.module.css';

type TabKey = 'url' | 'local';

export function QuickStartPage() {
  const [activeTab, setActiveTab] = useState<TabKey>('url');
  const [submitting, setSubmitting] = useState(false);
  const thresholds = useSettingsStore((state) => state.thresholds);
  const transcribeConfig = useSettingsStore((state) => state.transcribeConfig);

  const {
    status,
    runId,
    summaryText,
    trace,
    error,
    isRunning,
    handleExecutionResponse,
    reset,
  } = usePipelineExecution({
    onComplete: () => {
      message.success('处理完成');
      setSubmitting(false);
    },
    onError: (err) => {
      message.error(`处理失败: ${err}`);
      setSubmitting(false);
    },
  });

  // 处理 URL 提交
  const handleUrlSubmit = useCallback(
    async (url: string, options: PipelineOptions) => {
      setSubmitting(true);
      reset();

      try {
        const apiThresholds = {
          subtitle_coverage_min: thresholds.subtitleCoverageMin,
          transcript_token_per_min_min: thresholds.transcriptTokenPerMinMin,
          audio_rms_max_for_silence: thresholds.audioRmsMaxForSilence,
        };

        const mergedOptions: PipelineOptions = {
          transcribe_config: transcribeConfig,
          ...options,
        };

        const response = await runAutoUrl({
          inputs: { source_url: url },
          options: mergedOptions,
          thresholds: apiThresholds,
        });

        handleExecutionResponse(response.data);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
        setSubmitting(false);
      }
    },
    [reset, handleExecutionResponse, thresholds, transcribeConfig]
  );

  // 处理本地文件提交
  const handleLocalSubmit = useCallback(
    async (files: {
      subtitle_file_id?: string;
      audio_file_id?: string;
      video_file_id?: string;
    }) => {
      setSubmitting(true);
      reset();

      try {
        const apiThresholds = {
          subtitle_coverage_min: thresholds.subtitleCoverageMin,
          transcript_token_per_min_min: thresholds.transcriptTokenPerMinMin,
          audio_rms_max_for_silence: thresholds.audioRmsMaxForSilence,
        };

        const response = await runAutoLocal({
          inputs: {
            ...files,
          },
          thresholds: apiThresholds,
          options: {
            transcribe_config: transcribeConfig,
          },
        });

        handleExecutionResponse(response.data);
      } catch (err) {
        const errorMsg = err instanceof Error ? err.message : '请求失败';
        message.error(errorMsg);
        setSubmitting(false);
      }
    },
    [reset, handleExecutionResponse, thresholds, transcribeConfig]
  );

  // Tab 配置
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
      {/* 页面标题 */}
      <div className={styles.header}>
        <h1 className={styles.title}>视频摘要</h1>
        <p className={styles.description}>
          输入视频 URL 或上传本地文件，自动生成智能摘要
        </p>
      </div>

      {/* 输入区域 */}
      <div className={styles.inputSection}>
        <Tabs
          activeKey={activeTab}
          onChange={(key) => setActiveTab(key as TabKey)}
          items={tabItems}
          className={styles.tabs}
        />
      </div>

      {/* 结果展示 */}
      <ResultDisplay
        status={status}
        runId={runId}
        summaryText={summaryText}
        trace={trace}
        error={error}
        onReset={reset}
      />
    </div>
  );
}
