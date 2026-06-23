const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('hotspotApp', {
  runReport: () => ipcRenderer.invoke('run-report'),
  reportInfo: () => ipcRenderer.invoke('report-info'),
  dashboardData: () => ipcRenderer.invoke('dashboard-data'),
  saveKeywords: (keywords) => ipcRenderer.invoke('save-keywords', keywords),
  openConfig: () => ipcRenderer.invoke('open-config'),
  openFolder: () => ipcRenderer.invoke('open-folder'),
  openReportExternal: () => ipcRenderer.invoke('open-report-external'),
  openPromptDoc: () => ipcRenderer.invoke('open-prompt-doc'),
  onReportStatus: (callback) => {
    ipcRenderer.on('report-status', (_event, payload) => callback(payload));
  }
});
