/**
 * 设置页面
 */

import { Card, Form, Input, InputNumber, Select, Button, message, Space } from 'antd';
import { SaveOutlined, UndoOutlined } from '@ant-design/icons';
import { useShallow } from 'zustand/react/shallow';
import { useSettingsStore } from '@/stores/settingsStore';
import type { ThemeMode } from '@/config/theme';
import styles from './SettingsPage.module.css';

export function SettingsPage() {
  const {
    themeMode,
    apiBaseUrl,
    authToken,
    pollingInterval,
    requestTimeout,
    uploadMaxFileSizeMb,
    setThemeMode,
    setApiBaseUrl,
    setAuthToken,
    setPollingInterval,
    setRequestTimeout,
    setUploadMaxFileSizeMb,
    resetToDefaults,
  } = useSettingsStore(
    useShallow((state) => ({
      themeMode: state.themeMode,
      apiBaseUrl: state.apiBaseUrl,
      authToken: state.authToken,
      pollingInterval: state.pollingInterval,
      requestTimeout: state.requestTimeout,
      uploadMaxFileSizeMb: state.uploadMaxFileSizeMb,
      setThemeMode: state.setThemeMode,
      setApiBaseUrl: state.setApiBaseUrl,
      setAuthToken: state.setAuthToken,
      setPollingInterval: state.setPollingInterval,
      setRequestTimeout: state.setRequestTimeout,
      setUploadMaxFileSizeMb: state.setUploadMaxFileSizeMb,
      resetToDefaults: state.resetToDefaults,
    }))
  );

  const [form] = Form.useForm();

  const handleSave = () => {
    const values = form.getFieldsValue();

    setApiBaseUrl((values.apiBaseUrl || '').trim());
    setAuthToken(values.authToken || '');
    setPollingInterval(values.pollingInterval);
    setRequestTimeout(values.requestTimeout);
    setUploadMaxFileSizeMb(values.uploadMaxFileSizeMb);

    message.success('设置已保存');
  };

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
          authToken,
          pollingInterval,
          requestTimeout,
          uploadMaxFileSizeMb,
        }}
        className={styles.form}
      >
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

        <Card title="API 配置" className={styles.card}>
          <Form.Item
            label="API 基础地址"
            name="apiBaseUrl"
            tooltip="留空时使用同域路径；Web 常见值为空或 /apps/video，App 常见值为 https://<backend-domain>"
          >
            <Input placeholder="/apps/video 或 https://video-api.example.com" style={{ maxWidth: 460 }} />
          </Form.Item>

          <Form.Item
            label="Bearer Token（可选）"
            name="authToken"
            tooltip="留空表示不发送 Authorization 头"
          >
            <Input.Password placeholder="可选" style={{ maxWidth: 400 }} />
          </Form.Item>
        </Card>

        <Card title="请求行为" className={styles.card}>
          <div className={styles.thresholdGrid}>
            <Form.Item
              label="轮询间隔 (ms)"
              name="pollingInterval"
              tooltip="任务未完成时的状态轮询间隔"
            >
              <InputNumber min={500} max={10000} step={100} style={{ width: '100%' }} />
            </Form.Item>

            <Form.Item
              label="请求超时 (ms)"
              name="requestTimeout"
              tooltip="单次 API 请求的超时设置"
            >
              <InputNumber min={1000} max={600000} step={1000} style={{ width: '100%' }} />
            </Form.Item>
          </div>
        </Card>

        <Card title="上传限制" className={styles.card}>
          <Form.Item
            label="最大上传文件大小 (MB)"
            name="uploadMaxFileSizeMb"
            tooltip="仅用于前端校验，后端限制以服务端配置为准"
          >
            <InputNumber min={10} max={10240} step={50} style={{ width: 240 }} />
          </Form.Item>
        </Card>

        <div className={styles.actions}>
          <Space>
            <Button icon={<UndoOutlined />} onClick={handleReset}>
              恢复默认
            </Button>
            <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>
              保存设置
            </Button>
          </Space>
        </div>
      </Form>
    </div>
  );
}
