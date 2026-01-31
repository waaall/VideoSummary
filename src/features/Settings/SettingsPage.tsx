/**
 * 设置页面
 */

import { Card, Form, Input, InputNumber, Select, Button, Divider, message, Space } from 'antd';
import { SaveOutlined, UndoOutlined } from '@ant-design/icons';
import { useSettingsStore } from '@/stores';
import type { ThemeMode } from '@/config/theme';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const {
    themeMode,
    apiBaseUrl,
    thresholds,
    llmConfig,
    transcribeConfig,
    setThemeMode,
    setApiBaseUrl,
    updateThresholds,
    updateLLMConfig,
    updateTranscribeConfig,
    resetToDefaults,
  } = useSettingsStore();

  const [form] = Form.useForm();

  // 保存设置
  const handleSave = () => {
    const values = form.getFieldsValue();

    setApiBaseUrl(values.apiBaseUrl);
    updateThresholds({
      subtitleCoverageMin: values.subtitleCoverageMin,
      transcriptTokenPerMinMin: values.transcriptTokenPerMinMin,
      audioRmsMaxForSilence: values.audioRmsMaxForSilence,
    });
    updateLLMConfig({
      model: values.llmModel,
      maxTokens: values.llmMaxTokens,
      prompt: values.llmPrompt || undefined,
    });
    updateTranscribeConfig({
      model: values.transcribeModel,
      language: values.transcribeLanguage,
    });

    message.success('设置已保存');
  };

  // 重置设置
  const handleReset = () => {
    resetToDefaults();
    form.resetFields();
    message.info('已恢复默认设置');
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>设置</h1>
        <p className={styles.description}>配置应用参数和默认选项</p>
      </div>

      <Form
        form={form}
        layout="vertical"
        initialValues={{
          themeMode,
          apiBaseUrl,
          subtitleCoverageMin: thresholds.subtitleCoverageMin,
          transcriptTokenPerMinMin: thresholds.transcriptTokenPerMinMin,
          audioRmsMaxForSilence: thresholds.audioRmsMaxForSilence,
          llmModel: llmConfig.model,
          llmMaxTokens: llmConfig.maxTokens,
          llmPrompt: llmConfig.prompt || '',
          transcribeModel: transcribeConfig.model,
          transcribeLanguage: transcribeConfig.language,
        }}
        className={styles.form}
      >
        {/* 外观设置 */}
        <Card title="外观" className={styles.card}>
          <Form.Item label="主题模式" name="themeMode">
            <Select
              options={[
                { value: 'light', label: '浅色模式' },
                { value: 'dark', label: '深色模式' },
                { value: 'system', label: '跟随系统' },
              ]}
              onChange={(value: ThemeMode) => setThemeMode(value)}
              style={{ maxWidth: 200 }}
            />
          </Form.Item>
        </Card>

        {/* API 配置 */}
        <Card title="API 配置" className={styles.card}>
          <Form.Item
            label="API 基础地址"
            name="apiBaseUrl"
            rules={[{ required: true, message: '请输入 API 地址' }]}
          >
            <Input placeholder="http://localhost:8000" style={{ maxWidth: 400 }} />
          </Form.Item>
        </Card>

        {/* 阈值配置 */}
        <Card title="处理阈值" className={styles.card}>
          <div className={styles.thresholdGrid}>
            <Form.Item
              label="字幕覆盖率最小值"
              name="subtitleCoverageMin"
              tooltip="字幕时长覆盖视频时长的最小比例"
            >
              <InputNumber
                min={0}
                max={1}
                step={0.05}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item
              label="每分钟最小 Token 数"
              name="transcriptTokenPerMinMin"
              tooltip="转录文本每分钟的最小 Token 数量"
            >
              <InputNumber
                min={0}
                step={0.5}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item
              label="静音检测 RMS 阈值"
              name="audioRmsMaxForSilence"
              tooltip="低于此值认为是静音"
            >
              <InputNumber
                min={0}
                max={1}
                step={0.001}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </div>
        </Card>

        {/* LLM 配置 */}
        <Card title="LLM 摘要配置" className={styles.card}>
          <div className={styles.llmGrid}>
            <Form.Item label="默认模型" name="llmModel">
              <Select
                options={[
                  { value: 'gpt-3.5-turbo', label: 'GPT-3.5 Turbo' },
                  { value: 'gpt-4', label: 'GPT-4' },
                  { value: 'gpt-4-turbo', label: 'GPT-4 Turbo' },
                  { value: 'claude-3-haiku', label: 'Claude 3 Haiku' },
                  { value: 'claude-3-sonnet', label: 'Claude 3 Sonnet' },
                  { value: 'claude-3-opus', label: 'Claude 3 Opus' },
                ]}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item label="最大 Token 数" name="llmMaxTokens">
              <InputNumber
                min={100}
                max={8000}
                step={100}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </div>

          <Form.Item label="自定义 Prompt（可选）" name="llmPrompt">
            <Input.TextArea
              placeholder="留空使用系统默认 Prompt"
              rows={4}
              style={{ resize: 'vertical' }}
            />
          </Form.Item>
        </Card>

        {/* 转录配置 */}
        <Card title="语音转录配置" className={styles.card}>
          <div className={styles.transcribeGrid}>
            <Form.Item label="转录模型" name="transcribeModel">
              <Select
                options={[
                  { value: 'faster_whisper', label: 'Faster Whisper' },
                  { value: 'whisper_api', label: 'Whisper API' },
                  { value: 'whisper_cpp', label: 'Whisper.cpp' },
                ]}
                style={{ width: '100%' }}
              />
            </Form.Item>

            <Form.Item label="默认语言" name="transcribeLanguage">
              <Select
                options={[
                  { value: 'zh', label: '中文' },
                  { value: 'en', label: 'English' },
                  { value: 'ja', label: '日本語' },
                  { value: 'ko', label: '한국어' },
                  { value: 'auto', label: '自动检测' },
                ]}
                style={{ width: '100%' }}
              />
            </Form.Item>
          </div>
        </Card>

        <Divider />

        {/* 操作按钮 */}
        <div className={styles.actions}>
          <Space>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              onClick={handleSave}
            >
              保存设置
            </Button>
            <Button
              icon={<UndoOutlined />}
              onClick={handleReset}
            >
              恢复默认
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
}
