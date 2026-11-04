const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('sunbirdDesktop', {
  runtimeInfo: () => ipcRenderer.invoke('sunbird:runtime-info'),
  chooseDownloadDirectory: () => ipcRenderer.invoke('sunbird:choose-download-directory'),
  openDouyin: () => ipcRenderer.invoke('sunbird:open-douyin'),
  syncDouyinSession: () => ipcRenderer.invoke('sunbird:sync-douyin-session'),
  licenseStatus: () => ipcRenderer.invoke('sunbird:license-status'),
  activateLicense: (code) => ipcRenderer.invoke('sunbird:license-activate', code),
  refreshLicense: () => ipcRenderer.invoke('sunbird:license-refresh'),
  deactivateLicense: () => ipcRenderer.invoke('sunbird:license-deactivate')
})
