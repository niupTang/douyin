const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('sunbirdDesktop', {
  getPiSettings: () => ipcRenderer.invoke('sunbird:get-pi-settings'),
  savePiSettings: (settings) => ipcRenderer.invoke('sunbird:save-pi-settings', settings),
  piPrompt: (payload) => ipcRenderer.invoke('sunbird:pi-prompt', payload),
  runtimeInfo: () => ipcRenderer.invoke('sunbird:runtime-info'),
  chooseDownloadDirectory: () => ipcRenderer.invoke('sunbird:choose-download-directory'),
  openDouyin: () => ipcRenderer.invoke('sunbird:open-douyin'),
  syncDouyinSession: () => ipcRenderer.invoke('sunbird:sync-douyin-session'),
  licenseStatus: () => ipcRenderer.invoke('sunbird:license-status'),
  activateLicense: (code) => ipcRenderer.invoke('sunbird:license-activate', code),
  refreshLicense: () => ipcRenderer.invoke('sunbird:license-refresh'),
  deactivateLicense: () => ipcRenderer.invoke('sunbird:license-deactivate')
})
