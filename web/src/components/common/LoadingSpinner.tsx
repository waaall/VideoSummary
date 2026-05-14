/**
 * 加载动画组件
 */

import { Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';
import { CSSProperties } from 'react';

interface LoadingSpinnerProps {
  size?: 'small' | 'default' | 'large';
  tip?: string;
  fullScreen?: boolean;
}

export function LoadingSpinner({
  size = 'default',
  tip,
  fullScreen = false,
}: LoadingSpinnerProps) {
  const sizeMap = {
    small: 20,
    default: 32,
    large: 48,
  };

  const icon = (
    <LoadingOutlined
      style={{ fontSize: sizeMap[size] }}
      spin
    />
  );

  const containerStyle: CSSProperties = fullScreen
    ? {
        position: 'fixed',
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--glass-bg)',
        backdropFilter: 'blur(var(--glass-blur))',
        zIndex: 9999,
      }
    : {
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: 'var(--spacing-xl)',
      };

  return (
    <div style={containerStyle}>
      <Spin indicator={icon} tip={tip} size={size} />
    </div>
  );
}
