# Portal 双模式实现与部署指南（VideoSummary）

本文档定义 VideoSummary 前端在两种运行模式下的实现方式、构建方式和部署流程：

- `standalone`：子应用独立运行（开发、调试、单独对外）
- `portal`：子应用被统一入口 Portal 通过 `iframe` 挂载（子路径部署）

目标是同时满足：

- 单域名统一入口
- 子应用独立构建、独立发布、独立回滚
- 深链可访问
- 运行时隔离（路由、存储、Cookie）

---

## 1. 运行模式与环境变量

### 1.1 核心变量

| 变量 | 作用 | 示例（standalone） | 示例（portal） |
|---|---|---|---|
| `VITE_BASE_PATH` | Vite 构建资源前缀（`base`） | `/` | `/apps/video/` |
| `VITE_ROUTER_BASENAME` | React Router `basename` | `/` | `/apps/video` |
| `VITE_EMBEDDED` | 是否按“被挂载模式”渲染布局 | `false` | `true` |
| `VITE_STORAGE_NS` | 本地存储命名空间 | `video` | `video` |
| `VITE_COOKIE_PATH` | Cookie Path 隔离 | `/` | `/apps/video/` |

### 1.2 建议配置文件

建议在 `web/` 下维护：

- `.env.development`
- `.env.production`

建议内容如下。

```bash
# .env.development（开发）
VITE_BASE_PATH=/
VITE_ROUTER_BASENAME=/
VITE_EMBEDDED=false
VITE_STORAGE_NS=video
VITE_COOKIE_PATH=/
VITE_API_BASE_URL=http://localhost:8765
VITE_API_AUTH_TOKEN=
VITE_API_TIMEOUT=300000
VITE_POLLING_INTERVAL=2000
VITE_MAX_FILE_SIZE=524288000
```

```bash
# .env.production（Portal 生产）
VITE_BASE_PATH=/apps/video/
VITE_ROUTER_BASENAME=/apps/video
VITE_EMBEDDED=true
VITE_STORAGE_NS=video
VITE_COOKIE_PATH=/apps/video/
VITE_API_BASE_URL=/apps/video
VITE_API_AUTH_TOKEN=
VITE_API_TIMEOUT=300000
VITE_POLLING_INTERVAL=2000
VITE_MAX_FILE_SIZE=524288000
```

说明：

- 如需本机私有覆盖，使用 `.env.development.local` 或 `.env.production.local`。

---

## 2. 代码实现（当前仓库）

### 2.1 Vite base 与 HTML 变量注入

文件：`web/vite.config.ts`

实现点：

- 通过 `loadEnv(mode, process.cwd(), '')` 读取 `VITE_BASE_PATH`
- `base` 使用规范化函数，保证子路径结尾 `/`
- 使用 `transformIndexHtml` 注入 `__APP_STORAGE_NS__`

关键目的：

- 让 Portal 子路径构建时静态资源路径自动变成 `/apps/video/assets/...`
- 避免在 `index.html` 直接使用 `%VITE_STORAGE_NS%`（未定义时会告警）

### 2.2 Router basename

文件：`web/src/App.tsx`，`web/src/config/runtime.ts`

实现点：

- `BrowserRouter basename={runtimeConfig.routerBasename}`
- `runtimeConfig.routerBasename` 来自 `VITE_ROUTER_BASENAME`

结果：

- `portal` 下可直接访问 `/apps/video/history/...`
- 刷新与分享深链不丢失

### 2.3 embedded 模式布局

文件：`web/src/components/Layout/MainLayout.tsx`

实现点：

- 子应用头部拆分为“全局项 + 业务项”
- `standalone`：显示完整头部（全局项 + 业务项）
- `embedded`：仅显示业务项（应用内导航），全局项由 Portal 头部负责
- `embedded` 来源于 `VITE_EMBEDDED` 与 iframe 自动检测

### 2.4 本地存储命名空间

文件：`web/src/utils/storage.ts`

实现点：

- 统一封装 `appStorage`
- key 统一为 `${VITE_STORAGE_NS}:${key}`
- Zustand persist 通过 `createJSONStorage(() => appStateStorage)` 走同一封装

关联文件：

- `web/src/stores/settingsStore.ts`
- `web/src/stores/historyStore.ts`

### 2.5 Cookie Path 隔离

文件：`web/src/utils/cookie.ts`

实现点：

- `setCookie` 统一写入 `Path=${VITE_COOKIE_PATH}`
- 默认 `SameSite=Lax`

### 2.6 index.html 入口职责

文件：`web/index.html`

说明：

- 这是 Vite 项目的 HTML 入口（不是 CRA 的 `public/index.html`）
- React 实际入口是 `/src/main.tsx`
- 必须保留 `<div id="root"></div>`
- 主题预初始化脚本从 `${VITE_STORAGE_NS}:video-summary-settings` 读取主题
- `VITE_STORAGE_NS` 通过 `__APP_STORAGE_NS__` 在 Vite 构建时注入

### 2.7 健康检查文件

文件：`web/public/health.json`

用途：

- Portal 加载 iframe 前先请求 `/apps/video/health.json`
- 返回异常时展示“应用不可用/升级中”兜底页面

---

## 3. 构建与产物

工作目录：`web/`

```bash
# 开发（读取 .env.development）
npm run dev

# 生产构建（读取 .env.production）
npm run build
```

构建产物：

- `web/dist/index.html`
- `web/dist/assets/*`
- `web/dist/health.json`

Portal 模式期望：

- `dist/index.html` 中 JS/CSS 资源为 `/apps/video/assets/...`
- `dist/index.html` 中 `settingsKey` 为 `video:video-summary-settings`（或你设置的命名空间）

---

## 4. 部署拓扑

推荐拓扑：

- `https://example.com/`：Portal
- `https://example.com/apps/video/`：VideoSummary 静态资源目录
- `https://example.com/apps/qa/`：QA 静态资源目录

Portal 外部可用路由（用户可见）：

- `/video/*`：Portal 页面内显示 VideoSummary iframe
- `/qa/*`：Portal 页面内显示 QA iframe

Portal 内部实际资源路由（网关映射）：

- `/video/<rest>` -> `/apps/video/<rest>`
- `/qa/<rest>` -> `/apps/qa/<rest>`

---

## 5. Nginx 配置示例

以下示例只展示关键规则，实际路径按你的部署机目录调整。

```nginx
server {
  listen 80;
  server_name example.com;

  # Portal 主站
  location / {
    root /srv/www/portal;
    try_files $uri $uri/ /index.html;
  }

  # VideoSummary 子应用静态资源（独立 dist）
  location /apps/video/ {
    alias /srv/www/video/;                 # 指向 video dist 目录
    try_files $uri $uri/ /apps/video/index.html;
    add_header Cache-Control "public, max-age=300";
  }

  # QA 子应用静态资源（独立 dist）
  location /apps/qa/ {
    alias /srv/www/qa/;
    try_files $uri $uri/ /apps/qa/index.html;
    add_header Cache-Control "public, max-age=300";
  }
}
```

注意事项：

- `alias` 指向的目录应直接包含 `index.html` 和 `assets/`
- 必须保留 SPA 回退（`try_files ... /apps/video/index.html`）
- 子应用路径结尾 `/` 要与 `VITE_BASE_PATH` 一致

---

## 6. Portal 加载策略（最小实现）

Portal 对每个子应用维护配置：

- `appId`（如 `video`）
- `displayName`
- `routeBase`（如 `/video`）
- `entryUrl`（如 `/apps/video/`）
- `healthUrl`（如 `/apps/video/health.json`）

加载流程：

1. 路由命中 `/video/*`
2. 先 `fetch('/apps/video/health.json', { cache: 'no-store' })`
3. 成功后渲染 iframe：`src="/apps/video/..."`，高度 `calc(100vh - headerHeight)`
4. 失败则显示兜底文案（不可用/升级中）

---

## 7. 发布、灰度与回滚流程

### 7.1 独立发布（推荐）

1. 在 VideoSummary 仓库构建 `portal` 产物
2. 上传到 `/srv/www/video/`（或对象存储对应前缀）
3. 不改 Portal 代码即可生效（路径不变）

### 7.2 回滚

1. 保留历史版本目录（例如 `video-20260206-1`）
2. 通过软链接或目录切换快速回滚
3. 仅影响 `/apps/video/`，不影响 QA 与 Portal

### 7.3 验证项

1. `GET /apps/video/health.json` 返回 `status=ok`
2. 打开 `/video/` 能正常显示
3. 刷新 `/video/history` 不 404
4. 浏览器 `localStorage` key 带 `video:` 前缀
5. Cookie Path 为 `/apps/video/`（portal 模式）

---

## 8. 常见问题与排查

### 8.1 `base` 配置不生效

现象：

- 构建产物仍是 `/assets/...`

排查：

1. 确认 Vite 实际加载 `vite.config.ts`
2. 避免仓库内保留过时 `vite.config.js`
3. `npx vite build --debug` 查看 `configFile` 与 `rawBase`

### 8.2 子路径构建时报 `Failed to resolve /apps/video/src/main.tsx`

原因：

- `index.html` 入口脚本错误使用了 `%BASE_URL%src/main.tsx`

正确写法：

- `src="/src/main.tsx"`（让 Vite 自己重写）

### 8.3 `%VITE_STORAGE_NS% is not defined` 警告

原因：

- `index.html` 中直接使用 `%VITE_STORAGE_NS%`，未在环境中定义

当前方案：

- 使用 `__APP_STORAGE_NS__` 占位符，由 `vite.config.ts` 注入默认值

### 8.4 tsbuildinfo 被误提交

建议：

- `.gitignore` 中忽略 `web/*.tsbuildinfo`
- 已跟踪文件执行 `git rm --cached`

---

## 9. 接入新子应用（3~5 应用扩展）

接入新应用只做四件事：

1. 子应用实现同样环境变量契约（`BASE_PATH`、`BASENAME`、`EMBEDDED`、`STORAGE_NS`、`COOKIE_PATH`）
2. 产出独立 `dist/`，挂载到 `/apps/<appId>/`
3. Portal 增加一条应用配置（名称、路由、health、entry）
4. 网关增加对应静态目录与 SPA 回退规则

做到以上四点，即可保持“统一入口 + 独立演进 + 独立发布/回滚”。
