/**
 * 任务进度组件
 */

import { Steps } from 'antd';
import type { SummaryStatus } from '@/types/summary';
import styles from './JobProgress.module.css';

interface JobProgressProps {
  status: SummaryStatus | 'idle';
}

function getCurrentStep(status: SummaryStatus | 'idle') {
  if (status === 'idle') return 0;
  if (status === 'pending') return 0;
  if (status === 'running') return 1;
  return 2;
}

function getStepStatus(status: SummaryStatus | 'idle') {
  if (status === 'idle') return 'wait';
  if (status === 'failed') return 'error';
  if (status === 'completed') return 'finish';
  return 'process';
}

export function JobProgress({ status }: JobProgressProps) {
  const current = getCurrentStep(status);
  const stepStatus = getStepStatus(status);

  return (
    <div className={styles.container}>
      <Steps
        current={current}
        status={stepStatus}
        items={[
          { title: '已提交', description: '任务已创建并进入队列' },
          { title: '处理中', description: '正在生成摘要内容' },
          { title: '完成', description: '可查看最终摘要' },
        ]}
      />
    </div>
  );
}
