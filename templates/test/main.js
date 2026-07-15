const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const fs = require('fs');

let mainWindow;

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1300,
    height: 900,
    webPreferences: {
      nodeIntegration: true,      // يسمح لملف index.html باستخدام require('electron') مباشرة
      contextIsolation: false
    }
  });

  mainWindow.loadFile('index.html');
  // mainWindow.webContents.openDevTools(); // فعّل هذا السطر لو أردت أدوات المطور لتتبع الأخطاء
}

app.whenReady().then(() => {
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ============================================================
// اختيار المجلد الذي تريد إعادة تسمية الملفات بداخله
// ============================================================
ipcMain.handle('select-folder', async () => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openDirectory'],
    title: 'اختر المجلد الذي يحتوي الملفات المراد ترقيمها'
  });

  if (result.canceled || !result.filePaths.length) return null;
  return result.filePaths[0];
});

// ============================================================
// إعادة التسمية الفعلية على القرص
// ============================================================
ipcMain.handle('rename-files', async (event, { folderPath, renames }) => {
  const results = [];
  let successCount = 0;
  let errorCount = 0;

  for (const { oldName, newName } of renames) {
    const oldPath = path.join(folderPath, oldName);
    const newPath = path.join(folderPath, newName);

    try {
      // تأكد أن الملف الأصلي موجود فعلاً
      if (!fs.existsSync(oldPath)) {
        throw new Error('الملف الأصلي غير موجود في هذا المجلد');
      }

      // تجنّب الكتابة فوق ملف آخر موجود بنفس الاسم الجديد
      if (fs.existsSync(newPath) && oldPath !== newPath) {
        throw new Error('يوجد ملف آخر بنفس الاسم الجديد بالفعل');
      }

      fs.renameSync(oldPath, newPath);

      results.push({ oldName, newName, status: 'success' });
      successCount++;
    } catch (err) {
      results.push({ oldName, newName, status: 'error', message: err.message });
      errorCount++;
    }
  }

  return {
    results,
    summary: { success: successCount, error: errorCount }
  };
});
