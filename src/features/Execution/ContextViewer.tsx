/**
 * 上下文数据查看器组件
 */

import { useMemo, useState } from 'react';
import { Input, Tag, Empty } from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import styles from './ContextViewer.module.css';

interface ContextViewerProps {
  context: Record<string, unknown>;
}

// 值类型颜色
const typeColors: Record<string, string> = {
  string: 'green',
  number: 'blue',
  boolean: 'orange',
  object: 'purple',
  null: 'default',
};

// 格式化值显示
function formatValue(value: unknown): { display: string; type: string } {
  if (value === null) {
    return { display: 'null', type: 'null' };
  }
  if (value === undefined) {
    return { display: 'undefined', type: 'null' };
  }
  if (typeof value === 'string') {
    return { display: `"${value}"`, type: 'string' };
  }
  if (typeof value === 'number') {
    return { display: String(value), type: 'number' };
  }
  if (typeof value === 'boolean') {
    return { display: String(value), type: 'boolean' };
  }
  if (Array.isArray(value)) {
    return { display: `Array(${value.length})`, type: 'object' };
  }
  if (typeof value === 'object') {
    return { display: `Object(${Object.keys(value).length})`, type: 'object' };
  }
  return { display: String(value), type: 'string' };
}

export function ContextViewer({ context }: ContextViewerProps) {
  const [searchText, setSearchText] = useState('');
  const [expandedKeys, setExpandedKeys] = useState<Set<string>>(new Set());

  // 过滤和排序条目
  const entries = useMemo(() => {
    const all = Object.entries(context);

    if (!searchText) return all;

    const lower = searchText.toLowerCase();
    return all.filter(
      ([key, value]) =>
        key.toLowerCase().includes(lower) ||
        String(value).toLowerCase().includes(lower)
    );
  }, [context, searchText]);

  // 切换展开状态
  const toggleExpand = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) {
        next.delete(key);
      } else {
        next.add(key);
      }
      return next;
    });
  };

  if (Object.keys(context).length === 0) {
    return (
      <div className={styles.container}>
        <Empty description="暂无上下文数据" />
      </div>
    );
  }

  return (
    <div className={styles.container}>
      {/* 搜索框 */}
      <div className={styles.searchBar}>
        <Input
          placeholder="搜索键名或值..."
          prefix={<SearchOutlined />}
          value={searchText}
          onChange={(e) => setSearchText(e.target.value)}
          allowClear
          className={styles.searchInput}
        />
        <span className={styles.entryCount}>
          {entries.length} / {Object.keys(context).length} 条
        </span>
      </div>

      {/* 数据列表 */}
      <div className={styles.dataList}>
        {entries.map(([key, value]) => {
          const { display, type } = formatValue(value);
          const isExpandable = typeof value === 'object' && value !== null;
          const isExpanded = expandedKeys.has(key);

          return (
            <div key={key} className={styles.dataItem}>
              <div
                className={`${styles.dataRow} ${isExpandable ? styles.expandable : ''}`}
                onClick={() => isExpandable && toggleExpand(key)}
              >
                {isExpandable && (
                  <span className={`${styles.expandIcon} ${isExpanded ? styles.expanded : ''}`}>
                    ▶
                  </span>
                )}

                <span className={styles.dataKey}>{key}</span>

                <Tag color={typeColors[type]} className={styles.typeTag}>
                  {type}
                </Tag>

                {!isExpanded && (
                  <span className={styles.dataValue}>{display}</span>
                )}
              </div>

              {/* 展开的对象/数组 */}
              {isExpanded && isExpandable && (
                <pre className={styles.expandedValue}>
                  {JSON.stringify(value, null, 2)}
                </pre>
              )}
            </div>
          );
        })}

        {entries.length === 0 && searchText && (
          <div className={styles.noResults}>
            未找到匹配 "{searchText}" 的结果
          </div>
        )}
      </div>
    </div>
  );
}
