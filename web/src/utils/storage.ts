/**
 * 应用级存储封装
 * 强制 key 使用命名空间，避免多应用冲突
 */

import type { StateStorage } from 'zustand/middleware';
import { runtimeConfig } from '@/config/runtime';

function getStorageKey(key: string): string {
  return `${runtimeConfig.storageNamespace}:${key}`;
}

function getLocalStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export const appStorage = {
  key(key: string): string {
    return getStorageKey(key);
  },
  get(key: string): string | null {
    const storage = getLocalStorage();
    if (!storage) {
      return null;
    }
    return storage.getItem(getStorageKey(key));
  },
  set(key: string, value: string): void {
    const storage = getLocalStorage();
    if (!storage) {
      return;
    }
    storage.setItem(getStorageKey(key), value);
  },
  remove(key: string): void {
    const storage = getLocalStorage();
    if (!storage) {
      return;
    }
    storage.removeItem(getStorageKey(key));
  },
};

export const appStateStorage: StateStorage = {
  getItem: (key) => appStorage.get(key),
  setItem: (key, value) => appStorage.set(key, value),
  removeItem: (key) => appStorage.remove(key),
};
