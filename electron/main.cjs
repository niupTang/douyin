const { app, BrowserWindow, BaseWindow, WebContentsView, Menu, dialog, ipcMain, session, safeStorage } = require('electron')
const { spawn, spawnSync } = require('child_process')
const path = require('path')
const fs = require('fs')
const crypto = require('crypto')
const net = require('net')
const os = require('os')

// Some Windows environments cannot load Chromium's GPU subprocess. Keep the
// normal hardware-accelerated default, while allowing an explicit CPU-rendered
// compatibility launch before Electron reaches its ready event.
if (process.env.SAU_DISABLE_HARDWARE_ACCELERATION === '1') {
  app.disableHardwareAcceleration()
  app.commandLine.appendSwitch('disable-gpu')
  app.commandLine.appendSwitch('disable-software-rasterizer')
}

const BACKEND_PORT = process.env.SAU_BACKEND_PORT || '5409'
let backendProcess = null
let mainWindow = null
let douyinWindow = null
let douyinView = null
let douyinCloseView = null
const backendInstanceToken = crypto.randomUUID()
const isDevelopmentShell = () => Boolean(process.env.ELECTRON_START_URL)
const LICENSE_API_BASE = (
  process.env.SAU_LICENSE_API_BASE ||
  (app.isPackaged ? 'https://yichushiwu.club/watermark-api' : 'http://127.0.0.1:3001')
).replace(/\/$/, '')

function writeLog(message) {
  try {
    const logDir = app.isReady() ? app.getPath('userData') : __dirname
    fs.mkdirSync(logDir, { recursive: true })
    fs.appendFileSync(
      path.join(logDir, 'desktop.log'),
      `[${new Date().toISOString()}] ${message}\n`,
      'utf8'
    )
  } catch {
    // Logging must not crash the desktop shell.
  }
}

function getAppRoot() {
  if (app.isPackaged && !isDevelopmentShell()) {
    return path.join(process.resourcesPath, 'backend-source')
  }
  return path.join(__dirname, '..')
}

function getBackendExecutable() {
  if (!app.isPackaged || isDevelopmentShell()) {
    return null
  }
  const exe = path.join(process.resourcesPath, 'backend-runtime', 'sau_backend.exe')
  return fs.existsSync(exe) ? exe : null
}

function getBackendDataDir() {
  if (app.isPackaged && !isDevelopmentShell()) {
    return path.join(app.getPath('userData'), 'backend-data')
  }
  return getAppRoot()
}

function getPlaywrightBrowsersPath() {
  if (app.isPackaged) {
    const bundled = path.join(process.resourcesPath, 'ms-playwright')
    const chromium = path.join(bundled, 'chromium-1169', 'chrome-win', 'chrome.exe')
    const headless = path.join(
      bundled, 'chromium_headless_shell-1169', 'chrome-win', 'headless_shell.exe'
    )
    return fs.existsSync(chromium) && fs.existsSync(headless) ? bundled : null
  }
  const candidates = [
    process.env.PLAYWRIGHT_BROWSERS_PATH,
    path.join(getAppRoot(), 'ms-playwright'),
    path.join(getAppRoot(), 'build-resources', 'ms-playwright')
  ].filter(Boolean)

  for (const candidate of candidates) {
    if (/^c:[\\/]/i.test(path.resolve(candidate))) {
      continue
    }
    if (!fs.existsSync(candidate)) {
      continue
    }
    const hasBrowser = [
      path.join(candidate, 'chromium-1169', 'chrome-win', 'chrome.exe'),
      path.join(candidate, 'chromium_headless_shell-1169', 'chrome-win', 'headless_shell.exe')
    ].every((filename) => fs.existsSync(filename) && fs.statSync(filename).isFile())
    if (hasBrowser) {
      return candidate
    }
  }
  return null
}

function getBundledFfmpegDir() {
  const candidate = path.join(process.resourcesPath, 'ms-playwright', 'ffmpeg-1011')
  return app.isPackaged && fs.existsSync(candidate) ? candidate : null
}

function getBundledHuggingFaceHome() {
  const candidate = path.join(process.resourcesPath, 'huggingface')
  return app.isPackaged && fs.existsSync(candidate) ? candidate : null
}

function ensureBackendDataDir() {
  const dataDir = getBackendDataDir()
  for (const name of ['db', 'cookies', 'cookiesFile', 'videoFile', 'videos', 'logs']) {
    fs.mkdirSync(path.join(dataDir, name), { recursive: true })
  }
  return dataDir
}

function getPythonCommand(root) {
  const candidates = [
    path.join(root, '.venv', 'Scripts', 'python.exe'),
    process.env.PYTHON,
    'D:\\python\\python.exe',
    'python'
  ].filter(Boolean)
  for (const candidate of candidates) {
    if (path.isAbsolute(candidate) && !fs.existsSync(candidate)) continue
    const probe = spawnSync(candidate, ['-c', 'from flask import Blueprint; import sqlcipher3'], {
      cwd: root,
      windowsHide: true,
      timeout: 5000,
      stdio: 'ignore'
    })
    if (probe.status === 0) return candidate
  }
  return 'python'
}

function startBackend() {
  const root = getAppRoot()
  const backendExecutable = getBackendExecutable()
  const dataDir = ensureBackendDataDir()
  const playwrightBrowsersPath = getPlaywrightBrowsersPath()
  const browserCachePath = path.join(root, 'ms-playwright')
  const env = {
    ...process.env,
    SAU_APP_DIR: root,
    SAU_BASE_DIR: dataDir,
    SAU_BACKEND_PORT: BACKEND_PORT,
    SAU_INSTANCE_TOKEN: backendInstanceToken,
    SAU_PACKAGED: app.isPackaged ? '1' : '0'
  }
  if (playwrightBrowsersPath) {
    env.PLAYWRIGHT_BROWSERS_PATH = playwrightBrowsersPath
    env.SAU_BUNDLED_PLAYWRIGHT_PATH = playwrightBrowsersPath
  } else if (!/^c:[\\/]/i.test(path.resolve(browserCachePath))) {
    env.PLAYWRIGHT_BROWSERS_PATH = browserCachePath
  }
  const bundledFfmpegDir = getBundledFfmpegDir()
  if (bundledFfmpegDir) {
    env.SAU_FFMPEG_DIR = bundledFfmpegDir
    env.PATH = `${bundledFfmpegDir}${path.delimiter}${env.PATH || ''}`
  }
  const bundledHuggingFaceHome = getBundledHuggingFaceHome()
  if (bundledHuggingFaceHome) {
    env.SAU_BUNDLED_HUGGINGFACE_HOME = bundledHuggingFaceHome
    env.HF_HOME = bundledHuggingFaceHome
    env.HUGGINGFACE_HUB_CACHE = path.join(bundledHuggingFaceHome, 'hub')
  }

  writeLog(`Starting backend. packaged=${app.isPackaged}, dataDir=${dataDir}`)

  if (backendExecutable) {
    writeLog(`Using backend executable: ${backendExecutable}`)
    backendProcess = spawn(backendExecutable, [], {
      cwd: path.dirname(backendExecutable),
      env,
      windowsHide: true,
      stdio: 'ignore'
    })
  } else {
    const python = getPythonCommand(root)
    const backendEntry = path.join(root, 'sau_koubo_server.py')
    writeLog(`Using python backend: ${python} ${backendEntry}`)
    backendProcess = spawn(python, [backendEntry], {
      cwd: root,
      env,
      windowsHide: true,
      stdio: app.isPackaged ? 'ignore' : 'inherit'
    })
  }

  backendProcess.on('error', (error) => {
    writeLog(`Backend start failed: ${error.stack || error.message}`)
    dialog.showErrorBox('后端启动失败', error.message)
  })

  backendProcess.on('exit', (code) => {
    writeLog(`Backend exited with code: ${code}`)
    if (code !== 0 && !app.isQuitting) {
      dialog.showErrorBox('后端已退出', `本地服务异常退出，退出码：${code}`)
    }
  })
}

async function waitForBackend(retries = 60) {
  const url = `http://127.0.0.1:${BACKEND_PORT}/runtime/identity`
  for (let index = 0; index < retries; index += 1) {
    try {
      const response = await fetch(url, { method: 'OPTIONS' })
      if (response.ok || [200, 204, 400, 405].includes(response.status)) {
        writeLog(`Backend instance is reachable with status ${response.status}`)
        return true
      }
    } catch (error) {
      if (index === retries - 1) {
        writeLog(`Backend wait failed: ${error.message}`)
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  return false
}

function isBackendPortAvailable() {
  return new Promise((resolve) => {
    const server = net.createServer()
    server.once('error', () => resolve(false))
    server.once('listening', () => server.close(() => resolve(true)))
    server.listen(Number(BACKEND_PORT), '127.0.0.1')
  })
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 900,
    minWidth: 1100,
    minHeight: 720,
    title: 'Sunbird OS',
    backgroundColor: '#f6f7f9',
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
      preload: path.join(__dirname, 'preload.cjs')
    }
  })
  mainWindow = win

  if (process.env.ELECTRON_START_URL) {
    win.loadURL(process.env.ELECTRON_START_URL)
    return
  }

  win.loadFile(path.join(__dirname, '..', 'sau_frontend', 'dist', 'index.html'))
}

function isAllowedDouyinUrl(rawUrl) {
  try {
    const hostname = new URL(rawUrl).hostname.toLowerCase()
    return hostname === 'douyin.com' || hostname.endsWith('.douyin.com') ||
      hostname.endsWith('.douyincdn.com') || hostname.endsWith('.byteimg.com') ||
      hostname.endsWith('.pstatp.com') || hostname.endsWith('.snssdk.com')
  } catch {
    return false
  }
}

function openDouyinWindow() {
  if (douyinWindow && !douyinWindow.isDestroyed()) {
    douyinWindow.show()
    douyinWindow.focus()
    return
  }
  douyinWindow = new BaseWindow({
    width: 1280,
    height: 860,
    title: '抖音登录与验证',
    frame: false
  })
  douyinView = new WebContentsView({
    webPreferences: {
      partition: 'persist:douyin',
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  })
  douyinWindow.contentView.addChildView(douyinView)
  douyinCloseView = new WebContentsView({
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true
    }
  })
  douyinCloseView.setBackgroundColor('#00000000')
  douyinWindow.contentView.addChildView(douyinCloseView)
  douyinCloseView.webContents.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(`
    <!doctype html>
    <html><head><meta charset="utf-8"><style>
      * { box-sizing: border-box; }
      html, body { width: 100%; height: 100%; margin: 0; background: transparent; overflow: hidden; }
      body { display: flex; justify-content: center; align-items: center; }
      button { width: 34px; height: 34px; border: 0; border-radius: 10px; background: rgba(255,255,255,.94); color: #374151; display: grid; place-items: center; cursor: pointer; box-shadow: 0 2px 10px rgba(0,0,0,.18); }
      button:hover { background: #ef4444; color: #fff; }
      svg { width: 17px; height: 17px; }
    </style></head><body>
      <button aria-label="关闭抖音窗口" title="关闭" onclick="location.href='sunbird://close'"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M18 6 6 18M6 6l12 12"/></svg></button>
    </body></html>
  `)}`)
  const resize = () => {
    const [width, height] = douyinWindow.getContentSize()
    douyinView.setBounds({ x: 0, y: 0, width, height })
    douyinCloseView.setBounds({ x: Math.max(0, width - 48), y: 0, width: 48, height: 48 })
  }
  resize()
  douyinWindow.on('resize', resize)
  douyinView.webContents.setWindowOpenHandler(({ url }) => {
    if (isAllowedDouyinUrl(url)) douyinView.webContents.loadURL(url)
    return { action: 'deny' }
  })
  douyinView.webContents.on('will-navigate', (event, url) => {
    if (!isAllowedDouyinUrl(url)) event.preventDefault()
  })
  douyinCloseView.webContents.on('will-navigate', (event, url) => {
    event.preventDefault()
    if (url === 'sunbird://close' && douyinWindow && !douyinWindow.isDestroyed()) {
      douyinWindow.close()
    }
  })
  douyinWindow.on('closed', () => {
    if (douyinView && !douyinView.webContents.isDestroyed()) douyinView.webContents.close()
    if (douyinCloseView && !douyinCloseView.webContents.isDestroyed()) douyinCloseView.webContents.close()
    douyinView = null
    douyinCloseView = null
    douyinWindow = null
  })
  douyinView.webContents.loadURL('https://www.douyin.com/')
}

async function syncDouyinSession() {
  const cookies = await session.fromPartition('persist:douyin').cookies.get({})
  const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/runtime/douyin/session`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-SAU-Instance-Token': backendInstanceToken
    },
    body: JSON.stringify({ cookies: cookies.filter((cookie) => cookie.domain.includes('douyin')) })
  })
  if (!response.ok) throw new Error(`同步抖音会话失败：HTTP ${response.status}`)
  return response.json()
}

function registerDesktopIpc() {
  ipcMain.handle('sunbird:runtime-info', () => ({ desktop: true }))
  ipcMain.handle('sunbird:choose-download-directory', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
      title: '选择下载目录',
      properties: ['openDirectory', 'createDirectory']
    })
    return result.canceled ? null : result.filePaths[0]
  })
  ipcMain.handle('sunbird:open-douyin', () => {
    openDouyinWindow()
    return { opened: true }
  })
  ipcMain.handle('sunbird:sync-douyin-session', () => syncDouyinSession())
  ipcMain.handle('sunbird:license-status', () => getLicenseStatus())
  ipcMain.handle('sunbird:license-activate', (_event, code) => activateLicense(code))
  ipcMain.handle('sunbird:license-refresh', () => refreshLicense())
  ipcMain.handle('sunbird:license-deactivate', () => deactivateLicense())
}

function getLicenseStatePath() {
  return path.join(app.getPath('userData'), 'license-state.json')
}

function loadLicenseState() {
  try {
    if (!safeStorage.isEncryptionAvailable()) throw new Error('系统安全存储不可用')
    const stored = JSON.parse(fs.readFileSync(getLicenseStatePath(), 'utf8'))
    const decoded = safeStorage.decryptString(Buffer.from(stored.encrypted, 'base64'))
    return JSON.parse(decoded)
  } catch {
    return null
  }
}

function saveLicenseState(state) {
  if (!safeStorage.isEncryptionAvailable()) throw new Error('当前系统无法安全保存许可证')
  const encrypted = safeStorage.encryptString(JSON.stringify(state)).toString('base64')
  fs.writeFileSync(getLicenseStatePath(), JSON.stringify({ encrypted }), 'utf8')
}

function ensureDeviceIdentity() {
  const current = loadLicenseState() || {}
  if (!current.deviceId) {
    current.deviceId = `dev_${crypto.randomUUID().replace(/-/g, '')}`
    saveLicenseState(current)
  }
  return current
}

async function cloudLicenseRequest(endpoint, payload) {
  const requestUrl = `${LICENSE_API_BASE}/api/desktop/license/${endpoint}`
  writeLog(`License request started: ${endpoint}, method=POST, url=${requestUrl}`)
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 10000)
  try {
    const response = await fetch(requestUrl, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal: controller.signal
    })
    const result = await response.json().catch(() => ({}))
    if (!response.ok || result.code !== 0) {
      const error = new Error(result.message || result.msg || `授权服务请求失败：HTTP ${response.status}`)
      error.reasonCode = result.data?.reasonCode
      writeLog(`License request rejected: ${endpoint}, url=${requestUrl}, status=${response.status}, reason=${error.reasonCode || error.message}`)
      throw error
    }
    writeLog(`License request succeeded: ${endpoint}, url=${requestUrl}`)
    return result.data
  } finally {
    clearTimeout(timeout)
  }
}

async function installLicenseIntoBackend(state) {
  if (!state?.license || !state?.deviceId) return null
  const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/runtime/license/install`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-SAU-Instance-Token': backendInstanceToken
    },
    body: JSON.stringify({ license: state.license, deviceId: state.deviceId })
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok) {
    const error = new Error(result.message || '本地许可证验证失败')
    error.reasonCode = result.data?.reasonCode
    throw error
  }
  syncCliAccessToken(result.data?.token)
  return result.data
}

function syncCliAccessToken(token) {
  const configDirectory = path.join(app.getPath('appData'), 'Sunbird MCP')
  const configPath = path.join(configDirectory, 'config.json')
  try {
    fs.mkdirSync(configDirectory, { recursive: true })
    let config = {}
    try { config = JSON.parse(fs.readFileSync(configPath, 'utf8')) } catch {}
    if (token) config.token = token
    else delete config.token
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf8')
  } catch (error) {
    writeLog(`CLI token sync failed: ${error.message}`)
  }
}

async function activateLicense(code) {
  writeLog('License activation invoked')
  const state = ensureDeviceIdentity()
  const data = await cloudLicenseRequest('activate', {
    code: String(code || '').trim(),
    deviceId: state.deviceId,
    deviceName: os.hostname(),
    platform: process.platform,
    appId: 'sunbird-os',
    appVersion: app.getVersion()
  })
  const nextState = {
    deviceId: state.deviceId,
    refreshToken: data.refreshToken,
    license: data.license
  }
  saveLicenseState(nextState)
  return installLicenseIntoBackend(nextState)
}

async function refreshLicense() {
  const state = loadLicenseState()
  if (!state?.refreshToken || !state?.deviceId) return installLicenseIntoBackend(state)
  try {
    const data = await cloudLicenseRequest('refresh', {
      deviceId: state.deviceId,
      refreshToken: state.refreshToken,
      appVersion: app.getVersion()
    })
    const nextState = { ...state, license: data.license }
    saveLicenseState(nextState)
    return installLicenseIntoBackend(nextState)
  } catch (error) {
    // 网络不可达时使用仍处于签名离线期限内的本地许可证。
    if (error.name === 'AbortError' || !error.reasonCode) return installLicenseIntoBackend(state)
    throw error
  }
}

async function getLicenseStatus() {
  const state = loadLicenseState()
  if (!state?.license) return { license: { activated: false, valid: false, reasonCode: 'LICENSE_REQUIRED' } }
  try {
    return await installLicenseIntoBackend(state)
  } catch (error) {
    // A running desktop can cross the offline deadline without restarting.
    // Recover through the signed cloud refresh flow instead of asking for the code again.
    if (error.reasonCode === 'OFFLINE_GRACE_EXPIRED' && state.refreshToken) {
      try {
        return await refreshLicense()
      } catch (refreshError) {
        error = refreshError
      }
    }
    return { license: { activated: true, valid: false, reasonCode: error.reasonCode || 'LICENSE_INVALID', message: error.message } }
  }
}

async function deactivateLicense() {
  const state = loadLicenseState()
  if (state?.refreshToken) {
    await cloudLicenseRequest('deactivate', {
      deviceId: state.deviceId,
      refreshToken: state.refreshToken,
      appVersion: app.getVersion()
    })
  }
  try { fs.unlinkSync(getLicenseStatePath()) } catch {}
  syncCliAccessToken(null)
  await fetch(`http://127.0.0.1:${BACKEND_PORT}/runtime/license/clear`, {
    method: 'POST',
    headers: { 'X-SAU-Instance-Token': backendInstanceToken }
  })
  return { deactivated: true }
}

function getPiSettingsPath() {
  return path.join(app.getPath('userData'), 'pi-agent-settings.json')
}

function loadPiSettings() {
  try {
    const stored = JSON.parse(fs.readFileSync(getPiSettingsPath(), 'utf8'))
    let apiKey = ''
    if (stored.encryptedApiKey && safeStorage.isEncryptionAvailable()) {
      apiKey = safeStorage.decryptString(Buffer.from(stored.encryptedApiKey, 'base64'))
    }
    return { ...stored, encryptedApiKey: undefined, apiKey, apiKeyConfigured: Boolean(apiKey) }
  } catch {
    return { provider: 'deepseek', baseUrl: 'https://api.deepseek.com', model: 'deepseek-v4-flash', thinkingLevel: 'off', apiKey: '', apiKeyConfigured: false }
  }
}

async function migratePiSettingsToBackend() {
  const config = loadPiSettings()
  if (!config.apiKey) return { migrated: false, reason: 'no_legacy_key' }
  const response = await fetch(`http://127.0.0.1:${BACKEND_PORT}/runtime/ai/pi-credential`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-SAU-Instance-Token': backendInstanceToken
    },
    body: JSON.stringify({
      baseUrl: config.baseUrl,
      model: config.model,
      thinkingLevel: config.thinkingLevel,
      apiKey: config.apiKey
    })
  })
  const result = await response.json().catch(() => ({}))
  if (!response.ok || result.code !== 200) {
    throw new Error(result.message || 'PI Agent 配置迁移失败')
  }
  fs.unlinkSync(getPiSettingsPath())
  writeLog('Legacy PI Agent configuration migrated to backend AI runtime')
  return { migrated: true }
}

process.on('uncaughtException', (error) => {
  writeLog(`Uncaught exception: ${error.stack || error.message}`)
  dialog.showErrorBox('桌面程序异常', error.message)
})

process.on('unhandledRejection', (error) => {
  const message = error instanceof Error ? error.stack || error.message : String(error)
  writeLog(`Unhandled rejection: ${message}`)
})

app.whenReady().then(async () => {
  Menu.setApplicationMenu(null)
  writeLog('Electron app is ready')
  if (!(await isBackendPortAvailable())) {
    writeLog(`Backend port ${BACKEND_PORT} is already occupied; refusing to reuse it`)
    dialog.showErrorBox(
      '本地服务端口被占用',
      `端口 ${BACKEND_PORT} 已被其他程序占用。请关闭网页版后端或旧版 Sunbird OS 后重试。`
    )
    app.quit()
    return
  }
  startBackend()
  registerDesktopIpc()
  const ready = await waitForBackend()
  if (!ready) {
    dialog.showErrorBox('后端启动超时', '本地服务未能在 30 秒内启动，请查看 desktop.log。')
  }
  if (ready) {
    try { await migratePiSettingsToBackend() } catch (error) { writeLog(`PI Agent migration failed: ${error.message}`) }
    try { await refreshLicense() } catch (error) { writeLog(`License bootstrap failed: ${error.message}`) }
  }
  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('before-quit', () => {
  app.isQuitting = true
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill()
  }
  if (douyinWindow && !douyinWindow.isDestroyed()) douyinWindow.close()
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})
