const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('hotspotApp', {
  runReport: () => ipcRenderer.invoke('run-report'),
  reportInfo: () => ipcRenderer.invoke('report-info'),
  openConfig: () => ipcRenderer.invoke('open-config'),
  openFolder: () => ipcRenderer.invoke('open-folder'),
  openReportExternal: () => ipcRenderer.invoke('open-report-external'),
  onReportStatus: (callback) => {
    ipcRenderer.on('report-status', (_event, payload) => callback(payload));
  }
});

