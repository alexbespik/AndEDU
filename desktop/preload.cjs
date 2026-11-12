// The page's only bridge to the desktop shell: it can ask whether a Gemini key is stored, save or clear one.
// The key never comes back to the page.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sciedu', {
  isDesktop: true,
  platform: process.platform,  // for wording only (which keychain holds the key)
  hasKey: () => ipcRenderer.invoke('sciedu:hasKey'),
  saveKey: (key) => ipcRenderer.invoke('sciedu:saveKey', String(key)),
  clearKey: () => ipcRenderer.invoke('sciedu:clearKey'),
});
