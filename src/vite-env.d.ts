/// <reference types="vite/client" />

/**
 * 环境变量类型声明
 */
interface ImportMetaEnv {
  /** API 基础地址 */
  readonly VITE_API_BASE_URL?: string;
  /** API 请求超时时间（毫秒） */
  readonly VITE_API_TIMEOUT?: string;
  /** 轮询间隔（毫秒） */
  readonly VITE_POLLING_INTERVAL?: string;
  /** 最大上传文件大小（字节） */
  readonly VITE_MAX_FILE_SIZE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

/**
 * CSS 模块类型声明
 */
declare module '*.module.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare module '*.module.scss' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

/**
 * 静态资源类型声明
 */
declare module '*.svg' {
  const content: string;
  export default content;
}

declare module '*.png' {
  const content: string;
  export default content;
}

declare module '*.jpg' {
  const content: string;
  export default content;
}
