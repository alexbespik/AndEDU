// The page's only bridge to the desktop shell. Gemini keys are kept by the backend, per account
// (PUT /api/me/gemini-key); the shell only deletes the key older versions saved for the whole computer,
// once the backend has offered it to an account.
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('sciedu', {
  isDesktop: true,
  platform: process.platform,  // for wording only (which keychain holds the device key)
  removeLegacyKey: () => ipcRenderer.invoke('sciedu:removeLegacyKey'),
});
