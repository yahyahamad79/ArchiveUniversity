# ملف أوامر PowerShell لإعادة تسمية الملفات
# تاريخ الإنشاء: 15‏/7‏/2026، 4:19:02 م
# عدد الملفات: 2

# تعيين المجلد الحالي كمسار العمل
$folderPath = Get-Location

Write-Host "بدء عملية إعادة التسمية..." -ForegroundColor Cyan
Write-Host "عدد الملفات: 2" -ForegroundColor Yellow
Write-Host ""

$successCount = 0
$errorCount = 0


try {
    Rename-Item -Path "$oldName" -NewName "$newName" -ErrorAction Stop
    Write-Host "✅ تم: $oldName → $newName" -ForegroundColor Green
    $successCount++
} catch {
    Write-Host "❌ خطأ: $oldName → $newName" -ForegroundColor Red
    Write-Host "   السبب: $($_.Exception.Message)" -ForegroundColor Red
    $errorCount++
}

try {
    Rename-Item -Path "$oldName" -NewName "$newName" -ErrorAction Stop
    Write-Host "✅ تم: $oldName → $newName" -ForegroundColor Green
    $successCount++
} catch {
    Write-Host "❌ خطأ: $oldName → $newName" -ForegroundColor Red
    Write-Host "   السبب: $($_.Exception.Message)" -ForegroundColor Red
    $errorCount++
}

Write-Host ""
Write-Host "========== ملخص ==========" -ForegroundColor Cyan
Write-Host "✅ تم إعادة تسمية $successCount ملف بنجاح" -ForegroundColor Green
if ($errorCount -gt 0) {
    Write-Host "❌ فشل إعادة تسمية $errorCount ملف" -ForegroundColor Red
}
Write-Host "===========================" -ForegroundColor Cyan

Read-Host "اضغط Enter للخروج"
