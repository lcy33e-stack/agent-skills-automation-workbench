const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const rootDir = path.resolve(__dirname, '..');
const reportPath = path.join(rootDir, 'public', 'index.html');
const dataPath = path.join(rootDir, 'public', 'data', 'latest.json');
const iconPath = path.join(rootDir, 'assets', 'app-icon.ico');

let mainWindow;
let running = false;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 680,
    backgroundColor: '#f5f8fb',
    title: 'Agent Skills 自动化工作台',
    icon: iconPath,
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false
    }
  });

  mainWindow.removeMenu();
  mainWindow.loadFile(path.join(rootDir, 'app', 'index.html'));
}

function readLocalEnv() {
  const env = { ...process.env };
  for (const file of ['.env.local', '.env']) {
    const fullPath = path.join(rootDir, file);
    if (!fs.existsSync(fullPath)) continue;
    const lines = fs.readFileSync(fullPath, 'utf8').split(/\r?\n/);
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#') || !trimmed.includes('=')) continue;
      const index = trimmed.indexOf('=');
      const key = trimmed.slice(0, index).trim();
      const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, '');
      if (key && !env[key]) env[key] = value;
    }
  }
  return env;
}

function runReport() {
  if (running) {
    return Promise.resolve({ ok: false, message: '任务正在运行中' });
  }
  running = true;
  mainWindow?.webContents.send('report-status', { running: true, message: '正在抓取来源并生成运行结果...' });

  return new Promise((resolve) => {
    const child = spawn('python', ['scripts/run_pipeline.py'], {
      cwd: rootDir,
      env: readLocalEnv(),
      windowsHide: true
    });
    let stdout = '';
    let stderr = '';

    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('close', (code) => {
      running = false;
      const ok = code === 0;
      const message = ok ? stdout.trim() || '运行结果已刷新' : stderr.trim() || `运行失败，退出码 ${code}`;
      mainWindow?.webContents.send('report-status', { running: false, ok, message });
      resolve({ ok, message });
    });
  });
}

ipcMain.handle('run-report', runReport);
ipcMain.handle('report-info', () => {
  let generatedAt = null;
  let analysisStatus = 'unknown';
  if (fs.existsSync(dataPath)) {
    try {
      const data = JSON.parse(fs.readFileSync(dataPath, 'utf8'));
      generatedAt = data.generated_at;
      analysisStatus = data.stats?.analysis_status || 'unknown';
    } catch {
      analysisStatus = 'data parse error';
    }
  }
  return {
    reportUrl: `file://${reportPath.replace(/\\/g, '/')}`,
    reportExists: fs.existsSync(reportPath),
    generatedAt,
    analysisStatus
  };
});
ipcMain.handle('open-config', () => shell.openPath(path.join(rootDir, 'config', 'sources.yml')));
ipcMain.handle('open-folder', () => shell.openPath(rootDir));
ipcMain.handle('open-report-external', () => shell.openPath(reportPath));

app.whenReady().then(createWindow);
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) createWindow();
});
