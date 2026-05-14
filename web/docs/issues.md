# issues

记录当前issues

## 本地持久化问题

本地持久化没有版本/迁移策略。settingsStore.ts 与 historyStore.ts 使用 persist 但未设置 version/migrate。将来字段调整容易破坏旧数据；同时 apiKey 长期存 localStorage 有安全/合规风险。建议加版本与迁移函数，必要时改用 sessionStorage 或显式提示用户保存风险（client-localstorage-schema）。


## 低优先级

### 按需加载

重组件未按需加载。JobDetail.tsx 顶层引入 react-markdown 与 remark-gfm，即使用户不看摘要也会进入 bundle。建议在摘要 tab 渲染时动态 import() 或 React.lazy（bundle-dynamic-imports/bundle-conditional）。

### 多余更新

HistoryPage effect 依赖 jobs 导致多余执行。HistoryPage.tsx 的 useEffect 每次历史列表更新都会重新 selectJob，并可能触发额外 state 更新。建议将依赖收窄到 paramJobId，或用 selector 派生 existingJob 后仅在关键条件变化时执行（rerender-dependencies）。


### 条件渲染

条件渲染使用 &&（低影响）。ThemeToggle.tsx、HistoryList.tsx、HistoryListItem.tsx 里有 condition && <...>，Vercel 指南更推荐三元以避免潜在渲染 0 的问题（rendering-conditional-render）。

### URL 保护

- HistoryListItem.tsx 中 new URL(job.sourceUrl) 如果数据非法会抛异常导致列表渲染中断。建议 try/catch 或先走 isValidUrl。
