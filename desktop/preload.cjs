'use strict';
const {contextBridge, ipcRenderer} = require('electron');
const sessionToken = ipcRenderer.sendSync('framegrab:session-token');
contextBridge.exposeInMainWorld('framegrabNative', Object.freeze({
  sessionToken,
  version: () => ipcRenderer.invoke('framegrab:version'),
  chooseFolder: () => ipcRenderer.invoke('framegrab:choose-folder'),
  openFolder: () => ipcRenderer.invoke('framegrab:open-folder'),
  revealFile: id => ipcRenderer.invoke('framegrab:reveal-file', id),
  clipboardRead: () => ipcRenderer.invoke('framegrab:clipboard-read'),
  clipboardWrite: text => ipcRenderer.invoke('framegrab:clipboard-write', String(text).slice(0,20000)),
  updateStatus: () => ipcRenderer.invoke('framegrab:update-status'),
  updateSetFeed: url => ipcRenderer.invoke('framegrab:update-set-feed', url),
  updateCheck: () => ipcRenderer.invoke('framegrab:update-check'),
  updateDownload: () => ipcRenderer.invoke('framegrab:update-download'),
  updateInstall: () => ipcRenderer.invoke('framegrab:update-install'),
  diagnostics: () => ipcRenderer.invoke('framegrab:diagnostics'),
  openLogs: () => ipcRenderer.invoke('framegrab:open-logs'),
  onUpdate: callback => {
    if (typeof callback !== 'function') return () => {};
    const fn = (_event, detail) => callback(detail);
    ipcRenderer.on('framegrab:update-progress', fn);
    return () => ipcRenderer.removeListener('framegrab:update-progress', fn);
  }
}));
