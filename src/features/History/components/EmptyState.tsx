/**
 * 空状态组件（含 Job ID 查询输入框）
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Empty, Button, Divider, Input, message } from 'antd';
import { RocketOutlined, SearchOutlined } from '@ant-design/icons';
import styles from './EmptyState.module.css';

interface EmptyStateProps {
  hasHistory?: boolean;
}

export function EmptyState({ hasHistory = false }: EmptyStateProps) {
  const navigate = useNavigate();
  const [jobIdInput, setJobIdInput] = useState('');

  const handleSearch = (value: string) => {
    const trimmed = value.trim();
    if (!trimmed) {
      message.warning('请输入 Job ID');
      return;
    }
    navigate(`/history/${trimmed}`);
  };

  return (
    <div className={styles.container}>
      <Empty
        image={Empty.PRESENTED_IMAGE_SIMPLE}
        description={
          hasHistory
            ? '选择左侧任务查看详情'
            : '暂无历史任务'
        }
      />

      <div className={styles.actions}>
        <Button
          type="primary"
          icon={<RocketOutlined />}
          onClick={() => navigate('/')}
        >
          前往快速开始
        </Button>
      </div>

      <Divider className={styles.divider}>或</Divider>

      <div className={styles.searchSection}>
        <Input.Search
          placeholder="输入 Job ID 查询任务状态"
          value={jobIdInput}
          onChange={(e) => setJobIdInput(e.target.value)}
          onSearch={handleSearch}
          enterButton={
            <>
              <SearchOutlined /> 查询
            </>
          }
          className={styles.searchInput}
          allowClear
        />
      </div>
    </div>
  );
}
