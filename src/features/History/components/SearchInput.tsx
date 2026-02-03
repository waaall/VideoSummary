/**
 * 历史记录搜索框
 */

import { useCallback, useEffect, useState } from 'react';
import { Input } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import { historyConfig } from '@/config/history';
import styles from './SearchInput.module.css';

interface SearchInputProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export function SearchInput({
  value,
  onChange,
  placeholder = '搜索 URL / 标题 / Job ID...',
}: SearchInputProps) {
  const [localValue, setLocalValue] = useState(value);

  // 同步外部值变化
  useEffect(() => {
    setLocalValue(value);
  }, [value]);

  // 防抖处理
  const handleChange = useCallback(
    (inputValue: string) => {
      setLocalValue(inputValue);

      // 使用防抖延迟更新外部状态
      const timer = setTimeout(() => {
        onChange(inputValue);
      }, historyConfig.searchDebounce);

      return () => clearTimeout(timer);
    },
    [onChange]
  );

  return (
    <div className={styles.container}>
      <Input
        prefix={<SearchOutlined className={styles.icon} />}
        placeholder={placeholder}
        value={localValue}
        onChange={(e) => handleChange(e.target.value)}
        allowClear
        className={styles.input}
      />
    </div>
  );
}
