const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const { autoUpdater } = require('electron-updater');

let mainWindow;
let overlayWindow;
let pythonProcess = null;

// Auto-updater configuration
autoUpdater.autoDownload = false;
autoUpdater.autoInstallOnAppQuit = true;

// Settings file path
const settingsPath = path.join(app.getPath('userData'), 'settings.json');

// Auto-updater events
function setupAutoUpdater() {
    autoUpdater.on('checking-for-update', () => {
        console.log('Checking for updates...');
    });

    autoUpdater.on('update-available', (info) => {
        console.log('Update available:', info.version);
        if (mainWindow) {
            mainWindow.webContents.send('update-available', info);
        }
    });

    autoUpdater.on('update-not-available', () => {
        console.log('No updates available');
    });

    autoUpdater.on('error', (err) => {
        console.error('Auto-update error:', err);
    });

    autoUpdater.on('download-progress', (progress) => {
        if (mainWindow) {
            mainWindow.webContents.send('download-progress', progress);
        }
    });

    autoUpdater.on('update-downloaded', (info) => {
        console.log('Update downloaded');
        if (mainWindow) {
            mainWindow.webContents.send('update-downloaded', info);
        }
    });
}

function loadSettings() {
    try {
        if (fs.existsSync(settingsPath)) {
            return JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
        }
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
    return { steam_path: 'C:\\Program Files (x86)\\Steam\\steam.exe' };
}

function saveSettings(settings) {
    try {
        fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2));
    } catch (e) {
        console.error('Failed to save settings:', e);
    }
}

function createMainWindow() {
    mainWindow = new BrowserWindow({
        width: 1100,
        height: 700,
        minWidth: 900,
        minHeight: 600,
        frame: false,
        transparent: false,
        backgroundColor: '#0a0e14',
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js'),
            backgroundThrottling: false,
            devTools: false  // Disable DevTools for security
        },
        icon: path.join(__dirname, 'assets', 'icon.png')
    });

    mainWindow.loadFile('src/index.html');

    // Block DevTools keyboard shortcuts
    mainWindow.webContents.on('before-input-event', (event, input) => {
        // Block F12, Ctrl+Shift+I, Ctrl+Shift+J, Ctrl+Shift+C
        if (input.key === 'F12' ||
            (input.control && input.shift && ['I', 'i', 'J', 'j', 'C', 'c'].includes(input.key))) {
            event.preventDefault();
        }
    });
}

function createOverlayWindow() {
    overlayWindow = new BrowserWindow({
        fullscreen: true,
        frame: false,
        transparent: true,
        alwaysOnTop: true,
        skipTaskbar: true,
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    overlayWindow.loadFile('src/overlay.html');
    overlayWindow.setIgnoreMouseEvents(false);
    return overlayWindow;
}

// IPC Handlers
ipcMain.handle('window-minimize', () => mainWindow.minimize());
ipcMain.handle('window-maximize', () => {
    if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
    } else {
        mainWindow.maximize();
    }
});
ipcMain.handle('window-close', () => mainWindow.close());
ipcMain.handle('focus-window', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
        mainWindow.focus();
        mainWindow.webContents.focus();
    }
});

// Auto-update IPC handlers
ipcMain.handle('get-app-version', () => app.getVersion());
ipcMain.handle('check-for-updates', () => {
    return autoUpdater.checkForUpdates().catch(err => ({ error: err.message }));
});
ipcMain.handle('download-update', () => {
    autoUpdater.downloadUpdate();
});
ipcMain.handle('install-update', () => {
    autoUpdater.quitAndInstall();
});

ipcMain.handle('get-settings', () => loadSettings());
ipcMain.handle('save-settings', (event, settings) => {
    saveSettings(settings);
    return true;
});

ipcMain.handle('select-steam-path', async () => {
    const result = await dialog.showOpenDialog(mainWindow, {
        title: 'Select Steam Executable',
        filters: [{ name: 'Executable', extensions: ['exe'] }],
        properties: ['openFile']
    });
    if (!result.canceled && result.filePaths.length > 0) {
        return result.filePaths[0];
    }
    return null;
});

// Cloud sync via Python backend
ipcMain.handle('load-cloud-data', async () => {
    return new Promise((resolve, reject) => {
        const pythonScript = app.isPackaged
            ? path.join(process.resourcesPath, 'backend', 'cloud_sync.py')
            : path.join(__dirname, 'backend', 'cloud_sync.py');

        if (!fs.existsSync(pythonScript)) {
            reject(new Error('Cloud sync script not found'));
            return;
        }

        const proc = spawn('python', [pythonScript, '--load']);
        let output = '';
        let errorOutput = '';

        proc.stdout.on('data', (data) => {
            output += data.toString();
        });

        proc.stderr.on('data', (data) => {
            errorOutput += data.toString();
        });

        proc.on('close', (code) => {
            try {
                const result = JSON.parse(output.trim());
                resolve(result);
            } catch (e) {
                reject(new Error(errorOutput || 'Failed to parse cloud data'));
            }
        });

        proc.on('error', (err) => {
            reject(err);
        });
    });
});

ipcMain.handle('save-cloud-data', async (event, adminHash, accounts) => {
    return new Promise((resolve, reject) => {
        const pythonScript = app.isPackaged
            ? path.join(process.resourcesPath, 'backend', 'cloud_sync.py')
            : path.join(__dirname, 'backend', 'cloud_sync.py');

        if (!fs.existsSync(pythonScript)) {
            reject(new Error('Cloud sync script not found'));
            return;
        }

        // Write accounts to temp file to avoid command line length limits
        const tempDir = app.getPath('temp');
        const tempFile = path.join(tempDir, 'valtools_accounts.json');

        try {
            fs.writeFileSync(tempFile, JSON.stringify({
                admin_hash: adminHash,
                accounts: accounts
            }));
        } catch (e) {
            reject(new Error('Failed to write temp file: ' + e.message));
            return;
        }

        const args = [
            pythonScript,
            '--save-file', tempFile
        ];

        const proc = spawn('python', args);
        let output = '';
        let errorOutput = '';

        proc.stdout.on('data', (data) => {
            output += data.toString();
        });

        proc.stderr.on('data', (data) => {
            errorOutput += data.toString();
        });

        proc.on('close', (code) => {
            // Clean up temp file
            try { fs.unlinkSync(tempFile); } catch (e) { }

            try {
                const result = JSON.parse(output.trim());
                resolve(result);
            } catch (e) {
                reject(new Error(errorOutput || 'Failed to save cloud data'));
            }
        });

        proc.on('error', (err) => {
            try { fs.unlinkSync(tempFile); } catch (e) { }
            reject(err);
        });
    });
});

// Steam Guard Firebase sync via Python backend
ipcMain.handle('sg-login-admin', async (event, password) => {
    return runSteamGuardSync(['--action', 'login-admin', '--password', password]);
});

ipcMain.handle('sg-login-guest', async (event, code) => {
    return runSteamGuardSync(['--action', 'login-guest', '--code', code]);
});

ipcMain.handle('sg-setup-admin', async (event, password) => {
    return runSteamGuardSync(['--action', 'setup-admin', '--password', password]);
});

ipcMain.handle('sg-save-accounts', async (event, masterKey, accounts) => {
    return runSteamGuardSync(['--action', 'save-accounts', '--master-key', masterKey, '--accounts', JSON.stringify(accounts)]);
});

ipcMain.handle('sg-create-voucher', async (event, masterKey, days) => {
    return runSteamGuardSync(['--action', 'create-voucher', '--master-key', masterKey, '--days', days.toString()]);
});

function runSteamGuardSync(args) {
    return new Promise((resolve, reject) => {
        const pythonScript = app.isPackaged
            ? path.join(process.resourcesPath, 'backend', 'steamguard_sync.py')
            : path.join(__dirname, 'backend', 'steamguard_sync.py');

        if (!fs.existsSync(pythonScript)) {
            reject(new Error('Steam Guard sync script not found'));
            return;
        }

        const proc = spawn('python', [pythonScript, ...args]);
        let output = '';
        let errorOutput = '';

        proc.stdout.on('data', (data) => {
            output += data.toString();
        });

        proc.stderr.on('data', (data) => {
            errorOutput += data.toString();
        });

        proc.on('close', (code) => {
            try {
                const result = JSON.parse(output.trim());
                resolve(result);
            } catch (e) {
                reject(new Error(errorOutput || 'Failed to parse Steam Guard response'));
            }
        });

        proc.on('error', (err) => {
            reject(err);
        });
    });
}

ipcMain.handle('show-overlay', (event, text, subtext) => {
    if (!overlayWindow || overlayWindow.isDestroyed()) {
        overlayWindow = createOverlayWindow();
    }
    overlayWindow.show();
    overlayWindow.webContents.send('update-overlay', { text, subtext });
});

ipcMain.handle('hide-overlay', () => {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.hide();
    }
});

ipcMain.handle('update-overlay', (event, text, subtext, color) => {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.webContents.send('update-overlay', { text, subtext, color });
    }
});

ipcMain.handle('destroy-overlay', () => {
    if (overlayWindow && !overlayWindow.isDestroyed()) {
        overlayWindow.destroy();
        overlayWindow = null;
    }
});

// Python backend communication
ipcMain.handle('run-injection', async (event, accountData, steamPath) => {
    return new Promise((resolve, reject) => {
        const pythonScript = app.isPackaged
            ? path.join(process.resourcesPath, 'backend', 'automation.py')
            : path.join(__dirname, 'backend', 'automation.py');

        // Check if Python script exists
        if (!fs.existsSync(pythonScript)) {
            reject(new Error('Python automation script not found'));
            return;
        }

        console.log('Starting injection with:', {
            script: pythonScript,
            username: accountData.u,
            steamPath: steamPath
        });

        // Use shell: true on Windows to handle paths with spaces better
        pythonProcess = spawn('python', [
            pythonScript,
            '--username', accountData.u,
            '--password', accountData.p,
            '--steam-path', steamPath
        ], {
            shell: false,
            windowsHide: true
        });

        let output = '';
        let errorOutput = '';

        pythonProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n');
            for (const line of lines) {
                const trimmed = line.trim();
                if (!trimmed) continue;

                output += trimmed + '\n';
                console.log('Python:', trimmed);

                // Try to parse each line as JSON
                try {
                    const parsed = JSON.parse(trimmed);
                    if (parsed.type === 'status') {
                        mainWindow.webContents.send('injection-status', parsed);
                    }
                } catch (e) {
                    // Not JSON, ignore
                }
            }
        });

        pythonProcess.stderr.on('data', (data) => {
            const stderr = data.toString();
            errorOutput += stderr;
            console.error('Python stderr:', stderr);
        });

        pythonProcess.on('close', (code) => {
            console.log('Python process closed with code:', code);
            console.log('stderr:', errorOutput);
            pythonProcess = null;
            if (code === 0) {
                resolve({ success: true, output });
            } else {
                // Include stderr in error message
                const errorMsg = errorOutput.trim() || `Process exited with code ${code}`;
                reject(new Error(errorMsg));
            }
        });

        pythonProcess.on('error', (err) => {
            console.error('Python spawn error:', err);
            pythonProcess = null;
            reject(err);
        });
    });
});

ipcMain.handle('abort-injection', () => {
    if (pythonProcess) {
        pythonProcess.kill('SIGTERM');
        pythonProcess = null;
        return true;
    }
    return false;
});

app.whenReady().then(() => {
    createMainWindow();

    // Setup auto-updater and check for updates
    setupAutoUpdater();

    // Check for updates after 3 seconds
    setTimeout(() => {
        autoUpdater.checkForUpdates().catch(err => {
            console.error('Update check failed:', err);
        });
    }, 3000);

    app.on('activate', () => {
        if (BrowserWindow.getAllWindows().length === 0) {
            createMainWindow();
        }
    });
});

app.on('window-all-closed', () => {
    if (pythonProcess) {
        pythonProcess.kill();
    }
    if (process.platform !== 'darwin') {
        app.quit();
    }
});
