import os
import json
import shutil
from io import BytesIO
from datetime import datetime
import pandas as pd
from flask import Blueprint, render_template_string, request, send_file, jsonify

# إنشاء Blueprint للأرشيف لربطه بالسيرفر الرئيسي
archive_bp = Blueprint('archive', __name__)

# =====================================================================
# قالب الـ HTML لشاشة الأرشيف (مع زر النسخة الاحتياطية وتأمين الإحصائيات)
# =====================================================================
ARCHIVE_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>نظام أرشيف الطلاب</title>
    <style>
        :root { --navy:#123b5d; --blue:#1d6fa5; --mint:#1f9d79; --ink:#152536; --muted:#66788a; --line:#dce6ee; --surface:#fff; --soft:#f4f8fb; --shadow:0 14px 34px rgba(22, 55, 80, .10); }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { min-height:100vh; font-family:'Segoe UI', Tahoma, sans-serif; color:var(--ink); background:radial-gradient(circle at top right,#dceefa 0,transparent 34%), #f4f7fa; line-height:1.55; }
        .header { max-width:1240px; margin:22px auto 0; padding:26px 32px; border-radius:20px; background:linear-gradient(125deg,#123b5d,#1d6fa5); color:#fff; display:flex; justify-content:space-between; align-items:center; gap:22px; box-shadow:var(--shadow); }
        .header h1 { font-size:1.55rem; letter-spacing:-.3px; }
        .header-info { display:flex; gap:10px; flex-wrap:wrap; }
        .header-info span { display:block; padding:7px 11px; font-size:.78rem; border:1px solid rgba(255,255,255,.23); border-radius:9px; background:rgba(255,255,255,.10); direction:rtl; overflow-wrap:anywhere; }
        .settings-bar { max-width:1240px; margin:16px auto 0; padding:24px 28px; background:var(--surface); border:1px solid var(--line); border-radius:18px; box-shadow:0 8px 22px rgba(22,55,80,.05); }
        .settings-bar .settings-row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; padding:11px 0; border-bottom:1px solid #edf2f6; }
        .settings-bar .settings-row:last-of-type { border-bottom:0; }
        .settings-bar label { min-width:142px; font-weight:700; font-size:.9rem; color:#334d63; }
        .settings-bar input[type="text"] { flex:1 1 360px; min-width:220px; padding:11px 13px; border:1px solid #cbd9e4; outline:0; border-radius:10px; background:#fbfdff; color:#27445c; font-family:Consolas, monospace; transition:.2s; }
        .settings-bar input[type="text"]:focus, .search-input:focus { border-color:#2a8aca; box-shadow:0 0 0 4px rgba(42,138,202,.12); }
        .btn { min-height:40px; padding:9px 16px; border:1px solid transparent; border-radius:10px; font-family:inherit; font-weight:700; cursor:pointer; transition:transform .18s, box-shadow .18s, filter .18s; display: inline-flex; align-items: center; gap: 6px; }
        .btn:hover { transform:translateY(-1px); filter:brightness(1.03); box-shadow:0 6px 14px rgba(18,59,93,.16); }
        .btn:disabled { cursor:wait; transform:none; opacity:.7; }
        .btn-save { background:linear-gradient(135deg,#1f9d79,#167f66); color:#fff; }
        .btn-sync-all { background:linear-gradient(135deg,#f28b35,#d75b22); color:#fff; }
        .btn-backup-manual { background:linear-gradient(135deg,#495867,#343a40); color:#fff; }
        .btn-outline { background:#fff; border-color:#b8cad8; color:#24516e; }
        .status-msg { font-size:.8rem; padding:5px 10px; border-radius:8px; }
        .status-ok { background:#e4f8f0; color:#117355; }.status-warn { background:#fff6dc; color:#986a06; }.status-error { background:#fff0f0; color:#bc3b3b; }
        .action-bar,.search-container,.sync-report,.results-container { max-width:1120px; }
        .action-bar { margin:20px auto; padding:20px 24px; border:1px solid #f2c69a; border-radius:16px; background:linear-gradient(100deg,#fffaf4,#fff); display:flex; justify-content:space-between; align-items:center; gap:16px; box-shadow:0 8px 22px rgba(125,78,25,.06); flex-wrap: wrap; }
        .action-bar h3 { color:#9b4a16; }.action-bar p { margin-top:3px; color:var(--muted); }
        .action-buttons-group { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
        .search-container { margin:20px auto; padding:24px; background:var(--surface); border:1px solid var(--line); border-radius:16px; box-shadow:var(--shadow); }
        .search-input { width:100%; padding:12px 15px; border:1px solid #cbd9e4; outline:0; border-radius:10px; font:1rem inherit; transition:.2s; }
        .suggestions { background:#fff; border:1px solid #cddbe5; border-radius:10px; max-height:240px; overflow-y:auto; display:none; position:absolute; z-index:10; width:100%; margin-top:5px; box-shadow:0 12px 28px rgba(22,55,80,.16); }
        .suggestions.active { display:block; }.suggestion-item { padding:11px 14px; cursor:pointer; border-bottom:1px solid #edf2f6; }.suggestion-item:hover { background:#eff8fc; color:#155b87; }
        .student-card { background:#fff; border:1px solid var(--line); border-radius:16px; margin:0 0 18px; overflow:hidden; box-shadow:0 8px 24px rgba(22,55,80,.07); }
        .student-info { padding:21px 24px; border-bottom:1px solid #dce7ee; background:linear-gradient(100deg,#f9fcfe,#fff); display:flex; justify-content:space-between; align-items:center; gap:15px; flex-wrap:wrap; }.student-info h2 { font-size:1.2rem; color:#173e5b; }.student-info span { font-size:.88rem; color:#5d7487; }
        .summary-badge { padding:7px 12px; border-radius:999px; font-size:.85rem; font-weight:700; white-space:nowrap; margin-left: 5px; display: inline-block; }
        .summary-complete { background:#e4f8f0; color:#117355; }.summary-incomplete { background:#fff6dc; color:#986a06; }.summary-none { background:#fff0f0; color:#bc3b3b; }.summary-optional { background:#e8f3fc; color:#176b9e; }
        .doc-card { margin:10px 18px; padding:13px 15px; border:1px solid #e0e9ef; border-radius:11px; background:#fff; display:flex; align-items:center; gap:14px; transition:.18s; }.doc-card:hover { transform:translateX(-2px); box-shadow:0 5px 14px rgba(22,55,80,.07); }.doc-card.delivered { border-right:4px solid #1f9d79; }.doc-card.missing { border-right:4px solid #e65a5a; }.doc-card.optional { border-right:4px solid #2a8aca; }
        .file-tag { background:#edf6fc; color:#24618a; padding:5px 9px; border-radius:7px; cursor:pointer; display:inline-block; margin:2px; font-size:.83rem; }.file-tag:hover { background:#dceefa; }
        .modal { display:none; position:fixed; inset:0; background:rgba(10,28,42,.78); justify-content:center; align-items:center; z-index:1000; padding:20px; }.modal.active { display:flex; }.modal-content { background:#fff; width:min(1100px,100%); height:min(90vh,900px); border-radius:16px; overflow:hidden; display:flex; flex-direction:column; box-shadow:0 20px 55px rgba(0,0,0,.3); }.modal-header { padding:14px 20px; background:linear-gradient(135deg,#123b5d,#1d6fa5); color:#fff; display:flex; justify-content:space-between; align-items:center; }.modal-body { flex:1; overflow:auto; padding:16px; text-align:center; }
        .sync-report { padding:22px; margin:20px auto; border:1px solid #f2c69a; border-radius:16px; background:#fffdf9; box-shadow:var(--shadow); overflow:auto; }.sync-report h3 { color:#9b4a16; }.no-results,.loading { margin:20px auto; padding:38px 20px; max-width:720px; text-align:center; color:#6e8292; background:#fff; border:1px dashed #cbd9e4; border-radius:15px; }.btn-close { background:transparent; border:0; color:white; font-size:1.8rem; cursor:pointer; }.btn-folder { background:#244f70; color:#fff; padding:9px 14px; border-radius:9px; border:0; font-family:inherit; font-weight:700; cursor:pointer; }
        table { width:100%; border-collapse:collapse; margin-top:15px; overflow:hidden; border-radius:10px; } th,td { border-bottom:1px solid #e5edf3; padding:11px; text-align:right; } th { background:#edf5fa; color:#28516d; } tr:hover td { background:#fbfdfe; }
        .btn-back { background:#fff; border:1px solid rgba(255,255,255,0.4); color:white; padding: 7px 14px; border-radius: 9px; text-decoration: none; font-size: 0.85rem; font-weight: bold; background: rgba(255,255,255,0.15); transition: 0.2s; }
        .btn-back:hover { background: rgba(255,255,255,0.25); }
    </style>
</head>
<body>
<div class="header">
    <div style="display: flex; align-items: center; gap: 15px;">
        <a href="/" class="btn-back">🔙 شاشة التحكم</a>
        <h1>📁 نظام أرشيف الطلاب</h1>
    </div>
    <div class="header-info">
        <span>📂 الأرشيف: <strong id="archivePathDisplay">{{ archive_path or 'غير محدد' }}</strong></span>
        <span>📊 الإكسل: <strong id="excelPathDisplay">{{ excel_file or 'غير محدد' }}</strong></span>
        <span>📋 عدد الطلاب: <strong id="studentCount">0</strong></span>
    </div>
</div>

<div class="settings-bar">
    <div class="settings-row">
        <label>📂 مسار الأرشيف:</label>
        <input type="text" id="archivePathInput" value="{{ archive_path }}" placeholder="E:\\\\Archive" dir="ltr">
        <button class="btn btn-save" onclick="saveArchivePath()">💾 حفظ</button>
        <span id="archiveStatus"></span>
    </div>
    <div class="settings-row">
        <label>📊 مسار ملف الإكسل:</label>
        <input type="text" id="excelPathInput" value="{{ excel_file }}" placeholder="E:\\\\Archive\\\\Student_Index.xlsx" dir="ltr">
        <button class="btn btn-save" onclick="saveExcelPath()">💾 حفظ</button>
        <span id="excelStatus"></span>
    </div>
</div>

<div class="action-bar" id="actionBar" style="display: {{ 'none' if not archive_path else '' }};">
    <div><h3>🔄 أدوات إدارة بيانات المحفظة والأرشيف</h3><p style="font-size:0.8rem;">يمكنك عمل نسخة احتياطية فورية لملف الإكسل أو عمل مزامنة وتحديث شامل للحالات.</p></div>
    <div class="action-buttons-group">
        <button class="btn btn-backup-manual" id="btnManualBackup" onclick="triggerManualBackup()">🗄️ نسخة احتياطية من البيانات</button>
        <button class="btn btn-sync-all" id="btnSyncAll" onclick="syncAll()">🔄 تحديث شامل</button>
    </div>
</div>

<div id="syncReport" class="sync-report" style="display:none;"></div>

<div class="search-container" id="searchContainer" style="display: {{ 'none' if not archive_path else '' }};">
    <div style="display:flex;gap:10px;">
        <div style="position:relative;flex:2;" class="input-wrapper">
            <input type="text" id="searchInput" class="search-input" placeholder="🔍 اكتب الرقم الجامعي أو اسم الطالب..." autocomplete="off">
            <div id="suggestions" class="suggestions"></div>
        </div>
        <button class="btn btn-save" onclick="search()">🔍 بحث</button>
        <button class="btn btn-outline" onclick="clearResults()">🗑️ مسح</button>
    </div>
</div>

<div id="results" class="results-container" style="max-width:1000px; margin: 0 auto 50px auto;"></div>

<div id="viewerModal" class="modal">
    <div class="modal-content">
        <div class="modal-header"><h3 id="modalTitle">عرض الوثيقة</h3><button class="btn-close" onclick="closeViewer()">&times;</button></div>
        <div class="modal-body" id="modalBody"></div>
    </div>
</div>

<script>
    let archivePath = "{{ archive_path or '' }}";
    let excelPath = "{{ excel_file or '' }}";

    window.onload = () => {
        updateUI();
        if(archivePath) {
            document.getElementById('searchContainer').style.display = '';
            document.getElementById('actionBar').style.display = '';
            loadStats();
        }
    };

    function updateUI() {
        document.getElementById('archivePathDisplay').textContent = archivePath || 'غير محدد';
        document.getElementById('excelPathDisplay').textContent = excelPath || 'غير محدد';
    }

    async function saveArchivePath() {
        const path = document.getElementById('archivePathInput').value.trim();
        const s = document.getElementById('archiveStatus');
        if(!path) { s.className='status-msg status-error'; s.textContent='❌ أدخل مساراً'; return; }
        s.textContent='⏳...';
        try {
            const r = await fetch('/api/set-archive-path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({archive_path:path})});
            const d = await r.json();
            if(d.status==='ok') { archivePath=path; updateUI(); s.className='status-msg status-ok'; s.textContent='✅ '+d.folder_count+' مجلد'; document.getElementById('searchContainer').style.display=''; document.getElementById('actionBar').style.display=''; loadStats(); }
            else { s.className='status-msg status-error'; s.textContent='❌ '+d.message; }
        } catch(e) { s.className='status-msg status-error'; s.textContent='❌ خطأ اتصال بالخادم'; }
    }

    async function saveExcelPath() {
        const path = document.getElementById('excelPathInput').value.trim();
        const s = document.getElementById('excelStatus');
        s.textContent='⏳...';
        try {
            const r = await fetch('/api/set-excel-path',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({excel_file:path})});
            const d = await r.json();
            excelPath=path; updateUI();
            s.className = d.status==='ok' ? 'status-msg status-ok' : 'status-msg status-warn';
            s.textContent = (d.status==='ok'?'✅ ':'⚠️ ')+d.message;
            loadStats();
        } catch(e) { s.className='status-msg status-error'; s.textContent='❌ خطأ اتصال'; }
    }

    async function triggerManualBackup() {
        const btn = document.getElementById('btnManualBackup');
        if(!excelPath) { alert('يرجى تحديد وحفظ مسار ملف الإكسل أولاً لنسخه احتياطياً.'); return; }
        btn.disabled = true; btn.textContent = '⏳ جاري النسخ...';
        try {
            const r = await fetch('/api/manual-backup', { method: 'POST' });
            const d = await r.json();
            if(d.status === 'ok') {
                alert('✅ تم إنشاء نسخة احتياطية من ملف البيانات بنجاح!\\n\\nالمسار:\\n' + d.backup_path);
            } else {
                alert('❌ فشل النسخ الاحتياطي: ' + d.message);
            }
        } catch(e) {
            alert('❌ خطأ في الاتصال بالسيرفر أثناء إجراء النسخ الاحتياطي.');
        } finally {
            btn.disabled = false; btn.textContent = '🗄️ نسخة احتياطية من البيانات';
        }
    }

    async function syncAll() {
        const btn = document.getElementById('btnSyncAll');
        const reportDiv = document.getElementById('syncReport');
        if(!archivePath || !excelPath) { alert('يرجى حفظ مسارات الأرشيف والإكسل أولاً.'); return; }
        if(!confirm('سيتم تحديث الإكسل وملء مسارات المجلدات وتعديل الحالات الفردية. متابعة؟')) return;

        btn.disabled = true; btn.textContent = '⏳ جاري...';
        reportDiv.style.display = 'block'; reportDiv.innerHTML = '<div class="loading">⏳ جاري التحديث الشامل وفحص الملفات...</div>';

        try {
            const r = await fetch('/api/sync-all', { method: 'POST' });
            const d = await r.json();
            if(d.status === 'ok') {
                let html = `<h3>📊 تقرير التحديث الشامل للأرشيف</h3><p>🕐 ${d.timestamp}</p>`;
                html += `<span class="summary-badge summary-complete">✅ ${d.total_updates} تحديث (${d.updated_count} طالب)</span> `;
                html += `<p style="margin-top:10px;">💾 نسخة احتياطية تلقائية: ${d.backup_path||'غير متوفرة'}</p>`;
                if(d.updated_students && d.updated_students.length>0) {
                    html += '<table><tr><th>الرقم الجامعي</th><th>الاسم</th><th>التحديثات</th></tr>';
                    d.updated_students.forEach(s => { html += `<tr><td><strong>${s.student_id}</strong></td><td>${s.name||'-'}</td><td>${s.updates.join('<br>')}</td></tr>`; });
                    html += '</table>';
                }
                reportDiv.innerHTML = html;
            } else { reportDiv.innerHTML = `<div class="no-results"><h3>❌ فشل التحديث</h3><p>${d.message}</p></div>`; }
        } catch(e) { reportDiv.innerHTML = '<div class="no-results"><h3>❌ خطأ اتصال بالخادم</h3></div>'; }
        finally { btn.disabled = false; btn.textContent = '🔄 تحديث شامل'; loadStats(); }
    }

    async function loadStats() {
        try { 
            const r = await fetch('/api/stats'); 
            const d = await r.json(); 
            document.getElementById('studentCount').textContent = d.student_count || 0; 
        } catch(e){}
    }

    async function search() {
        if(!archivePath) return;
        const q = document.getElementById('searchInput').value.trim();
        if(!q) return;
        const div = document.getElementById('results');
        div.innerHTML='<div class="loading">⏳ جاري البحث عن البيانات...</div>';
        try {
            const r = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
            const data = await r.json();
            if(!data || !data.length) { div.innerHTML='<div class="no-results">📭 لا توجد نتائج مطابقة في الأرشيف.</div>'; return; }
            let html = '';
            data.forEach(s=>{
                const sum = s.summary;
                let sc='summary-none', st='';
                
                if(sum && sum.total_required >= 0) {
                    if(sum.is_complete) { sc='summary-complete'; st=`✅ مكتمل (${sum.delivered}/${sum.total_required})`; }
                    else if(sum.delivered > 0) { sc='summary-incomplete'; st=`⚠️ ناقص (${sum.delivered}/${sum.total_required})`; }
                    else { sc='summary-none'; st=`❌ لم يسلم (0/${sum.total_required})`; }
                }

                let optionalBadgeHtml = '';
                if(sum && sum.total_optional > 0) {
                    optionalBadgeHtml = `<span class="summary-badge summary-optional">➖ اختيارية (${sum.delivered_optional}/${sum.total_optional})</span>`;
                }

                html += `<div class="student-card">
                    <div class="student-info">
                        <div><h2>${s.full_name||'طالب بدون اسم'}</h2><span>📌 الرقم: ${s.student_id}</span></div>
                        <div>
                            <span class="summary-badge ${sc}">${st}</span>
                            ${optionalBadgeHtml}
                        </div>
                        <button class="btn-folder" onclick="openFolder('${s.student_id}')">📂 فتح المجلد</button>
                    </div><div style="padding:10px 20px;">`;
                
                if(s.documents) s.documents.forEach(d=>{
                    html += `<div class="doc-card ${d.card_class}">
                        <div style="min-width:140px; font-weight:bold;">${d.status_display}</div>
                        <div style="flex:1;">${d.doc_name}</div>
                        <div>${d.files&&d.files.length?d.files.map(f=>`<span class="file-tag" onclick="viewDocument('${s.student_id}','${f.filename}')">👁️ ${f.filename}</span>`).join(''):'<span style="color:#bbb;">لا يوجد ملف مادي</span>'}</div>
                    </div>`;
                });
                html += '</div></div>';
            });
            div.innerHTML = html;
        } catch(e) { div.innerHTML='<div class="no-results"><h3>❌ حدث خطأ برمي</h3></div>'; }
    }

    function clearResults() { document.getElementById('searchInput').value=''; document.getElementById('results').innerHTML=''; }
    
    function viewDocument(sid, fn) {
        const modal = document.getElementById('viewerModal');
        document.getElementById('modalTitle').textContent = fn;
        const url = `/api/view/${sid}/${encodeURIComponent(fn)}`;
        const ext = fn.split('.').pop().toLowerCase();
        const body = document.getElementById('modalBody');
        if(['jpg','jpeg','png','gif'].includes(ext)) body.innerHTML = `<img src="${url}" style="max-width:100%; max-height: 75vh;">`;
        else if(ext==='pdf') body.innerHTML = `<iframe src="${url}" style="width:100%;height:75vh; border:none;"></iframe>`;
        else body.innerHTML = `<div style="padding:50px;"><a href="${url}" class="btn btn-save" download>⬇&nbsp; تحميل وقراءة الملف محلياً</a></div>`;
        modal.classList.add('active');
    }

    function closeViewer() { document.getElementById('viewerModal').classList.remove('active'); }
    
    async function openFolder(id) {
        try { const response = await fetch(`/api/open-folder/${encodeURIComponent(id)}`); if (!response.ok) alert('تعذر فتح مجلد الطالب.'); } catch (error) { alert('تعذر الاتصال بالخادم.'); }
    }

    document.getElementById('viewerModal').addEventListener('click', function(e){ if(e.target===this) closeViewer(); });
    document.addEventListener('keydown', function(e){ if(e.key==='Escape') { closeViewer(); } });

    let st;
    document.getElementById('searchInput').addEventListener('input', function(){
        clearTimeout(st); const q = this.value.trim();
        if(q.length<1) { document.getElementById('suggestions').classList.remove('active'); return; }
        st = setTimeout(()=>fetchSuggestions(q), 300);
    });

    async function fetchSuggestions(q) {
        if(!archivePath) return;
        try {
            const r = await fetch(`/api/suggest?q=${encodeURIComponent(q)}`);
            const d = await r.json(); const div = document.getElementById('suggestions');
            if(!d || !d.length) { div.classList.remove('active'); return; }
            div.innerHTML = d.map(i=>`<div class="suggestion-item" onclick="selectSuggestion('${i.student_id}')">${i.full_name} — ${i.student_id}</div>`).join('');
            div.classList.add('active');
        } catch(e){}
    }

    function selectSuggestion(id) { document.getElementById('searchInput').value=id; document.getElementById('suggestions').classList.remove('active'); search(); }
    document.addEventListener('click', function(e){ if(!e.target.closest('.input-wrapper')) document.getElementById('suggestions').classList.remove('active'); });
    document.getElementById('searchInput').addEventListener('keypress', function(e){ if(e.key==='Enter'){ document.getElementById('suggestions').classList.remove('active'); search(); } });
</script>
</body>
</html>
"""

class ConfigManager:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.config_file = os.path.join(base_dir, "config", "archive_config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {'archive_path': '', 'excel_file': ''}

    def save_config(self, archive_path, excel_file):
        self.config['archive_path'] = archive_path
        self.config['excel_file'] = excel_file
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    @property
    def archive_path(self): return self.config.get('archive_path', '')
    @archive_path.setter
    def archive_path(self, value): self.config['archive_path'] = value; self.save_config(value, self.excel_file)
    @property
    def excel_file(self): return self.config.get('excel_file', '')
    @excel_file.setter
    def excel_file(self, value): self.config['excel_file'] = value; self.save_config(self.archive_path, value)

class DocTypeManager:
    def __init__(self, base_dir):
        self.doc_types_file = os.path.join(base_dir, "config", "doc_types.json")
        self.default_types = {
            "document_types": {
                "شهادة ثانوية": {"name_ar": "شهادة ثانوية عامة", "name_en": "High School Certificate", "code": "HS", "required": True, "order": 1},
                "شهادة ميلاد": {"name_ar": "شهادة ميلاد", "name_en": "Birth Certificate", "code": "BC", "required": True, "order": 2},
                "صورة هوية": {"name_ar": "صورة هوية", "name_en": "ID Card", "code": "ID", "required": True, "order": 3},
                "صور شخصية": {"name_ar": "صور شخصية", "name_en": "Personal Photos", "code": "PH", "required": True, "order": 4},
                "كشف علامات": {"name_ar": "كشف علامات", "name_en": "Transcript", "code": "TR", "required": False, "order": 5}
            }
        }
        self.data = self._load_or_create()

    def _load_or_create(self):
        if not os.path.exists(self.doc_types_file):
            os.makedirs(os.path.dirname(self.doc_types_file), exist_ok=True)
            with open(self.doc_types_file, 'w', encoding='utf-8') as f:
                json.dump(self.default_types, f, ensure_ascii=False, indent=2)
            return self.default_types
        try:
            with open(self.doc_types_file, 'r', encoding='utf-8') as f: return json.load(f)
        except: return self.default_types

    def save_types(self, data):
        os.makedirs(os.path.dirname(self.doc_types_file), exist_ok=True)
        with open(self.doc_types_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        self.data = data

    def get_types_info(self): return self.data.get('document_types', {})
    def get_ordered_columns(self): return [col for col, info in sorted(self.get_types_info().items(), key=lambda x: x[1].get('order', 999))]
    def is_required(self, col_name): return self.get_types_info()[col_name].get('required', True) if col_name in self.get_types_info() else True

class ExcelRepository:
    def __init__(self, config_manager):
        self.config_manager = config_manager

    def get_resolved_path(self):
        path = self.config_manager.excel_file
        if path and os.path.exists(path): return path
        return ''

    def backup(self):
        excel_path = self.get_resolved_path()
        if not excel_path: return None
        backup_path = excel_path.replace('.xlsx', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
        try: shutil.copy2(excel_path, backup_path); return backup_path
        except: return None

    def check_permission(self):
        excel_path = self.get_resolved_path()
        if not excel_path: return False
        try:
            with open(excel_path, 'a'): return True
        except: return False

    def normalize_student_id_series(self, df):
        if df.empty or 'student_id' not in df.columns: return df
        df = df.copy()
        df['student_id'] = df['student_id'].apply(lambda v: '' if pd.isna(v) else str(v).strip())
        return df

    def load_students_df(self):
        path = self.get_resolved_path()
        if path:
            try:
                df = pd.read_excel(path, sheet_name='Students', converters={'student_id': lambda x: '' if pd.isna(x) else str(x).strip()})
                return self.normalize_student_id_series(df)
            except: pass
        return pd.DataFrame()

class ArchiveService:
    def __init__(self, config_manager, doc_manager, excel_repo):
        self.config = config_manager
        self.doc_manager = doc_manager
        self.repo = excel_repo

    def normalize_id(self, value):
        if value is None or pd.isna(value): return ''
        s = str(value).strip()
        if s.endswith('.0') and s[:-2].isdigit(): s = s[:-2]
        return s.lstrip('0') if s.lstrip('0') != '' else s

    def id_matches(self, value, query):
        return str(value).strip() == str(query).strip() or self.normalize_id(value) == self.normalize_id(query)

    def resolve_student_folder(self, student_id):
        if not self.config.archive_path: return None
        folder = os.path.join(self.config.archive_path, str(student_id).strip())
        if os.path.isdir(folder): return folder
        folder_norm = os.path.join(self.config.archive_path, self.normalize_id(student_id))
        if os.path.isdir(folder_norm): return folder_norm
        return None

    def sync_all_students(self):
        if not self.config.archive_path: return {'status': 'error', 'message': 'مسار الأرشيف غير صحيح.'}
        excel = self.repo.get_resolved_path()
        if not excel or not self.repo.check_permission(): return {'status': 'error', 'message': 'المسار غير محدد أو الملف مفتوح حالياً.'}
        backup_path = self.repo.backup()
        try:
            df = pd.read_excel(excel, sheet_name='Students', converters={'student_id': lambda x: '' if pd.isna(x) else str(x).strip()})
            df = self.repo.normalize_student_id_series(df)
            if 'folder_path' not in df.columns: df['folder_path'] = ''
            
            self.doc_manager.data = self.doc_manager._load_or_create()
            fresh_types = self.doc_manager.get_types_info()
            
            code_mapping = {info.get('code', '').upper(): col for col, info in fresh_types.items() if info.get('code')}
            core_cols = ['student_id', 'full_name', 'college', 'status', 'enrollment_year', 'folder_path']
            
            for col in fresh_types:
                if col not in df.columns:
                    df[col] = '✗' if fresh_types[col].get('required', True) else ''

            doc_cols = [c for c in df.columns if c not in core_cols and c in fresh_types]
            total_updates, folders_filled = 0, 0
            updated_students = []

            for item in os.listdir(self.config.archive_path):
                if item.lower() in ['stud_data', '__pycache__', '.git']: continue
                folder_path = os.path.join(self.config.archive_path, item)
                if not os.path.isdir(folder_path): continue
                try: files = os.listdir(folder_path)
                except: continue
                
                mask = df['student_id'].apply(lambda v: self.id_matches(v, item))
                if not mask.any(): continue
                
                student_updates = []
                for dcol in doc_cols:
                    current_val = str(df.loc[mask, dcol].iloc[0]).strip() if not df.loc[mask, dcol].empty else ''
                    if current_val in ['✓', '✔', '✅', '1', 'TRUE', 'True', 'نعم']: continue
                    
                    found = False
                    for f in files:
                        if dcol in f or (code_mapping.get(f.split('.')[0].upper()) == dcol): found = True; break
                    
                    if found:
                        sym = '✓' if self.doc_manager.is_required(dcol) else '✅'
                        df.loc[mask, dcol] = sym
                        student_updates.append(f'{dcol} ← {sym}')
                        total_updates += 1

                cp = str(df.loc[mask, 'folder_path'].iloc[0]).strip() if not df.loc[mask, 'folder_path'].empty else ''
                if cp in ['', 'nan', 'None']:
                    df.loc[mask, 'folder_path'] = folder_path
                    folders_filled += 1
                    student_updates.append('تحديث مسار المجلد')

                if student_updates:
                    name = df.loc[mask, 'full_name'].iloc[0]
                    updated_students.append({'student_id': item, 'name': str(name) if not pd.isna(name) else '', 'updates': student_updates})

            if total_updates > 0 or folders_filled > 0:
                try: dt_df = pd.read_excel(excel, sheet_name='DocumentTypes')
                except: dt_df = None
                with pd.ExcelWriter(excel, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='Students', index=False)
                    if dt_df is not None: dt_df.to_excel(writer, sheet_name='DocumentTypes', index=False)
            return {'status': 'ok', 'total_updates': total_updates, 'folders_filled': folders_filled, 'updated_count': len(updated_students), 'updated_students': updated_students, 'backup_path': backup_path, 'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        except Exception as e: return {'status': 'error', 'message': str(e)}

    def get_student_documents(self, student_id):
        df = self.repo.load_students_df()
        if df.empty: return []
        mask = df['student_id'].apply(lambda v: self.id_matches(v, student_id))
        student_row = df[mask].iloc[0].to_dict() if mask.any() else {}
        folder_path = self.resolve_student_folder(student_id) or os.path.join(self.config.archive_path, str(student_id))
        
        self.doc_manager.data = self.doc_manager._load_or_create()
        types_info = self.doc_manager.get_types_info()
        
        actual_files = {}
        if os.path.exists(folder_path):
            for filename in os.listdir(folder_path):
                file_path = os.path.join(folder_path, filename)
                if os.path.isfile(file_path): actual_files[filename] = {'path': file_path}

        documents = []
        for doc_col in self.doc_manager.get_ordered_columns():
            doc_arabic_name = types_info[doc_col]['name_ar'] if doc_col in types_info else doc_col
            is_req = self.doc_manager.is_required(doc_col)
            
            matched_files = [{'filename': fn} for fn in actual_files if doc_col in fn or (types_info[doc_col].get('code') and types_info[doc_col].get('code').upper() in fn.upper())]
            has_physical_file = len(matched_files) > 0

            status = str(student_row.get(doc_col, '')).strip() if doc_col in student_row else ''
            
            if status in ['✓', '✔', '1', 'TRUE', 'True', 'نعم', '✅'] or has_physical_file:
                status_display = '✅ تم التسليم' if is_req else '✅ سلّم (تطوعي)'
                c_cls = 'delivered'
            elif is_req:
                status_display = '❌ لم يسلم'
                c_cls = 'missing'
            else:
                status_display = '➖ غير مطلوبة'
                c_cls = 'optional'

            documents.append({'doc_name': doc_arabic_name, 'doc_column': doc_col, 'is_required': is_req, 'status_display': status_display, 'files': matched_files, 'card_class': c_cls})
        return documents

    def get_delivery_summary(self, student_id):
        docs = self.get_student_documents(student_id)
        if not docs: return None
        
        required = [d for d in docs if d['is_required']]
        missing_req = [d for d in required if '❌' in d['status_display']]
        
        optional = [d for d in docs if not d['is_required']]
        delivered_opt = [d for d in optional if '✅' in d['status_display']]
        
        return {
            'total_required': len(required),
            'delivered': len(required) - len(missing_req),
            'total_optional': len(optional),
            'delivered_optional': len(delivered_opt),
            'missing_names': [d['doc_name'] for d in missing_req],
            'is_complete': len(missing_req) == 0
        }

def init_archive_routes(base_dir):
    config_manager = ConfigManager(base_dir)
    doc_manager = DocTypeManager(base_dir)
    repo = ExcelRepository(config_manager)
    service = ArchiveService(config_manager, doc_manager, repo)

    @archive_bp.route('/archive')
    def archive_screen():
        return render_template_string(ARCHIVE_TEMPLATE, archive_path=config_manager.archive_path, excel_file=config_manager.excel_file)

    @archive_bp.route('/api/set-archive-path', methods=['POST'])
    def set_archive_path():
        data = request.get_json() or {}; path = data.get('archive_path', '').strip()
        if not path or not os.path.exists(path): return jsonify({'status': 'error', 'message': 'المسار المادي غير موجود'})
        config_manager.archive_path = path
        folders = [f for f in os.listdir(path) if os.path.isdir(os.path.join(path, f))]
        return jsonify({'status': 'ok', 'folder_count': len(folders)})

    @archive_bp.route('/api/set-excel-path', methods=['POST'])
    def set_excel_path():
        data = request.get_json() or {}; path = data.get('excel_file', '').strip()
        if not path or not os.path.exists(path): return jsonify({'status': 'warning', 'message': 'تم حفظ المسار لكن الملف غير موجود حالياً في هذا المسار'})
        config_manager.excel_file = path
        return jsonify({'status': 'ok', 'message': f'تم الحفظ والتحقق بنجاح.'})

    @archive_bp.route('/api/sync-all', methods=['POST'])
    def sync_all_api(): return jsonify(service.sync_all_students())

    # 🗄️ ممر السيرفر الجديد للنسخ الاحتياطي اليدوي بطلب من المستخدم
    @archive_bp.route('/api/manual-backup', methods=['POST'])
    def manual_backup_api():
        if not repo.get_resolved_path():
            return jsonify({'status': 'error', 'message': 'مسار ملف الإكسل غير معرّف.'}), 400
        if not repo.check_permission():
            return jsonify({'status': 'error', 'message': 'الملف مفتوح حالياً في برنامج آخر (مثل Excel). يرجى إغلاقه والمحاولة مجدداً.'}), 400
        
        backup_path = repo.backup()
        if backup_path:
            return jsonify({'status': 'ok', 'backup_path': backup_path})
        else:
            return jsonify({'status': 'error', 'message': 'فشل نسخ الملف، تأكد من الصلاحيات والمساحة المتاحة.'}), 500

    @archive_bp.route('/api/stats')
    def stats():
        df = repo.load_students_df()
        return jsonify({
            'student_count': len(df) if not df.empty else 0
        })

    @archive_bp.route('/api/search')
    def search():
        query = request.args.get('q', '').strip()
        if not query or not config_manager.archive_path: return jsonify([])
        df = repo.load_students_df()
        students = []
        mask = df['student_id'].apply(lambda v: service.id_matches(v, query)) if not df.empty else pd.Series([False])
        if not mask.any() and not df.empty and 'full_name' in df.columns:
            mask = df['full_name'].astype(str).str.contains(query, case=False, na=False)
        matched_df = df[mask] if not df.empty and mask.any() else pd.DataFrame()
        
        if not matched_df.empty:
            for _, row in matched_df.iterrows():
                sid = str(row['student_id']).strip()
                students.append({'student_id': sid, 'full_name': row.get('full_name', ''), 'documents': service.get_student_documents(sid), 'summary': service.get_delivery_summary(sid)})
        return jsonify(students)

    @archive_bp.route('/api/suggest')
    def api_suggest():
        query = request.args.get('q', '').strip()
        df = repo.load_students_df()
        suggestions = []
        if not df.empty:
            mask = df['student_id'].astype(str).str.contains(query) | df['full_name'].astype(str).str.contains(query)
            for _, row in df[mask].head(8).iterrows():
                suggestions.append({'student_id': str(row['student_id']), 'full_name': row['full_name']})
        return jsonify(suggestions)

    @archive_bp.route('/api/view/<student_id>/<path:filename>')
    def view_file(student_id, filename):
        folder = service.resolve_student_folder(student_id) or os.path.join(config_manager.archive_path, str(student_id))
        return send_file(os.path.join(folder, filename))

    @archive_bp.route('/api/open-folder/<student_id>')
    def open_folder(student_id):
        folder = service.resolve_student_folder(student_id) or os.path.join(config_manager.archive_path, str(student_id))
        if os.path.exists(folder): os.startfile(folder); return jsonify({'status': 'ok'})
        return jsonify({'status': 'error'}), 404

    return archive_bp