/**
 * URL 输入组件
 */

import { useState, useCallback, useMemo } from 'react';
import { Input, Button, Collapse, Form, InputNumber, Select, Space, message } from 'antd';
import { PlayCircleOutlined, SettingOutlined, LinkOutlined } from '@ant-design/icons';
import { isValidUrl, isSupportedVideoUrl } from '@/utils/validators';
import { useSettingsStore } from '@/stores';
import type { SummaryOptions, PipelineOptions } from '@/types/api';
import styles from './UrlInput.module.css';

interface UrlInputProps {
  onSubmit: (url: string, options: PipelineOptions) => void;
  loading?: boolean;
}

export function UrlInput({ onSubmit, loading = false }: UrlInputProps) {
  const [url, setUrl] = useState('');
  const [showAdvanced, setShowAdvanced] = useState(false);

  // 从设置中获取默认值
  const summaryOptions = useSettingsStore((state) => state.summaryOptions);

  // 高级选项表单
  const [form] = Form.useForm<{
    workDir: string;
    model: string;
    maxTokens: number;
    prompt: string;
  }>();

  // URL 验证状态
  const urlStatus = useMemo(() => {
    if (!url) return { valid: false, message: '' };
    if (!isValidUrl(url)) return { valid: false, message: '请输入有效的 URL' };
    if (!isSupportedVideoUrl(url)) {
      return { valid: true, message: '此 URL 可能不受支持，但仍可尝试处理', warning: true };
    }
    return { valid: true, message: '' };
  }, [url]);

  // 提交处理
  const handleSubmit = useCallback(() => {
    if (!url || !urlStatus.valid) {
      message.error('请输入有效的视频 URL');
      return;
    }

    const formValues = form.getFieldsValue();

    // 构建选项
    const options: PipelineOptions = {};

    if (formValues.workDir) {
      options.work_dir = formValues.workDir;
    }

    // LLM 摘要选项
    const summary: SummaryOptions = {
      model: formValues.model || summaryOptions.model,
      max_tokens: formValues.maxTokens || summaryOptions.max_tokens,
      prompt: formValues.prompt || undefined,
    };

    options.summary = summary;

    onSubmit(url, options);
  }, [url, urlStatus.valid, form, onSubmit]);

  // 高级选项配置
  const advancedItems = [
    {
      key: 'advanced',
      label: (
        <span className={styles.advancedLabel}>
          <SettingOutlined />
          高级选项
        </span>
      ),
      children: (
        <Form
          form={form}
          layout="vertical"
          initialValues={{
            workDir: '/tmp/downloads',
            model: summaryOptions.model,
            maxTokens: summaryOptions.max_tokens,
            prompt: summaryOptions.prompt || '',
          }}
          className={styles.advancedForm}
        >
          <Form.Item label="工作目录" name="workDir">
            <Input placeholder="/tmp/downloads" />
          </Form.Item>

          <Space size="middle" wrap>
            <Form.Item label="LLM 模型" name="model" style={{ marginBottom: 0 }}>
              <Select
                style={{ width: 180 }}
                options={[
                  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
                  { value: 'gpt-4', label: 'GPT-4' },
                  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
                  { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
                  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
                ]}
              />
            </Form.Item>

            <Form.Item label="最大 Token" name="maxTokens" style={{ marginBottom: 0 }}>
              <InputNumber min={100} max={4000} step={100} style={{ width: 120 }} />
            </Form.Item>
          </Space>

          <Form.Item label="自定义 Prompt（可选）" name="prompt">
            <Input.TextArea
              placeholder="留空使用默认 Prompt"
              rows={3}
              style={{ resize: 'vertical' }}
            />
          </Form.Item>
        </Form>
      ),
    },
  ];

  return (
    <div className={styles.container}>
      {/* URL 输入区 */}
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

      {/* 验证提示 */}
      {url && urlStatus.message && (
        <p className={`${styles.hint} ${urlStatus.warning ? styles.warning : styles.error}`}>
          {urlStatus.message}
        </p>
      )}

      {/* 高级选项 */}
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
