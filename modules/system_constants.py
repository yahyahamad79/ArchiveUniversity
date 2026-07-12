import os
import json
import pandas as pd
from flask import Blueprint, render_template_string, request, jsonify
from modules.archive_update import DocTypeManager, ConfigManager, ExcelRepository

# إنشاء Blueprint خاص بثوابت النظام
constants_bp = Blueprint('constants', __name__)

CONSTANTS_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>ثوابت النظام - أنواع الوثائق</title>
    <style>
        :root { --navy:#123b5d; --blue:#1d6fa5; --mint:#1f9d79; --ink:#152536; --muted:#66788a; --line:#dce6ee; --surface:#fff; --soft:#f4f8fb; --shadow:0 14px 34px rgba(22, 55, 80, .10); }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { min-height:100vh; font-family:'Segoe UI', Tahoma, sans-serif; color:var(--ink); background:#f4f7fa; line-height:1.55; }
        .header { max-width:1100px; margin:22px auto 0; padding:26px 32px; border-radius:20px; background:linear-gradient(125deg,#123b5d,#244f70); color:#fff; display:flex; justify-content:space-between; align-items:center; box-shadow:var(--shadow); }
        .header h1 { font-size:1.55rem; }
        .btn-back { background:rgba(255,255,255,0.15); border:1px solid rgba(255,255,255,0.4); color:white; padding:7px 14px; border-radius:9px; text-decoration:none; font-size:0.85rem; font-weight:bold; transition:0.2s; }
        .btn-back:hover { background:rgba(255,255,255,0.25); }
        .content-container { max-width:1100px; margin:24px auto; padding:30px; background:var(--surface); border:1px solid var(--line); border-radius:18px; box-shadow:var(--shadow); }
        .help-text { color:#60768a; font-size:.9rem; margin-bottom:20px; }
        .doc-types-table-wrap { overflow:auto; border:1px solid #dce6ee; border-radius:10px; margin-bottom:20px; }
        table { width:100%; border-collapse:collapse; text-align:right; }
        th, td { padding:12px; border-bottom:1px solid #edf2f6; }
        th { background:#edf5fa; color:#28516d; font-weight:700; }
        input[type="text"], input[type="number"] { width:100%; padding:8px 10px; border:1px solid #cbd9e4; border-radius:7px; color:#27445c; font-family:inherit; }
        input[type="text"]:focus, input[type="number"]:focus { outline:0; border-color:#2a8aca; box-shadow:0 0 0 3px rgba(42,138,202,.10); }
        .doc-code-input { direction:ltr; text-transform:uppercase; font-family:monospace; }
        .doc-required-cell { text-align:center; }
        .btn { min-height:40px; padding:9px 18px; border:1px solid transparent; border-radius:10px; font-weight:700; cursor:pointer; transition:.18s; display: inline-flex; align-items: center; gap: 6px; }
        .btn-save { background:linear-gradient(135deg,#1f9d79,#167f66); color:#fff; }
        .btn-save:hover { box-shadow:0 6px 14px rgba(31,157,121,.2); }
        .btn-sync { background:linear-gradient(135deg, #6652a6, #4e3b8c); color:#fff; }
        .btn-sync:hover { box-shadow:0 6px 14px rgba(102,82,166,.2); }
        .btn-outline { background:#fff; border-color:#b8cad8; color:#24516e; margin-bottom:15px; }
        .btn-remove-doc { padding:6px 9px; color:#b73737; background:#fff0f0; border:1px solid #f1c2c2; border-radius:7px; cursor:pointer; }
        .actions-row { display:flex; justify-content:flex-end; align-items:center; gap:15px; border-top:1px solid #edf2f6; padding-top:20px; flex-wrap: wrap; }
        .status-msg { font-size:0.9rem; margin-left:auto; font-weight:bold; }
        .status-ok { color:#117355; }
        .status-error { color:#bc3b3b; }
        .status-warn { color:#b27d06; }
    </style>
</head>
<body>

<div class="header">
    <h1>⚙️ ثوابت النظام — واجهة إعداد أنواع الوثائق Doc_Type</h1>
    <a href="/" class="btn-back">🔙 شاشة التحكم</a>
</div>

<div class="content-container">
    <p class="help-text">💡 أدخل الحقول التالية لتحديد أنواع الوثائق المعتمدة. الاسم الداخلي يُمثل اسم العمود المطابق لملف الـ Excel. يرجى الضغط على حفظ التعديلات أولاً، ثم القيام بالمزامنة لتطبيقها على ملف الإكسل.</p>
    
    <button class="btn btn-outline" type="button" onclick="addDocTypeRow()">＋ إضافة نوع وثيقة جديد</button>

    <div class="doc-types-table-wrap">
        <table>
            <thead>
                <tr>
                    <th>الاسم الداخلي (العمود)</th>
                    <th>الاسم بالعربية</th>
                    <th>الاسم بالإنجليزية</th>
                    <th>الرمز الخاص (Code)</th>
                    <th>الترتيب البصري</th>
                    <th style="text-align:center;">وثيقة إلزامية</th>
                    <th>الإجراء</th>
                </tr>
            </thead>
            <tbody id="docTypesRows"></tbody>
        </table>
    </div>

    <div class="actions-row">
        <span id="editorStatus" class="status-msg"></span>
        <label style="margin-left: 20px; font-size: 0.9rem; font-weight: bold; color: #334d63; cursor:pointer;">
            <input type="checkbox" id="allowDeleteCheckbox"> السماح بحذف الأعمدة غير المستخدمة من ملف الإكسل
        </label>
        <button class="btn btn-save" onclick="saveDocTypesEditor()">💾 حفظ التعديلات</button>
        <button class="btn btn-sync" onclick="syncColumnsFromConstants()">🔄 مزامنة وتطبيق الأعمدة في الإكسل</button>
    </div>
</div>

<script>
    window.onload = () => { loadDocTypes(); };

    function escapeValue(value) {
        return String(value ?? '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    function addDocTypeRow(columnName = '', info = {}) {
        const rows = document.getElementById('docTypesRows');
        const order = info.order ?? (rows.children.length + 1);
        rows.insertAdjacentHTML('beforeend', `
            <tr>
                <td><input class="doc-column-input" type="text" value="${escapeValue(columnName)}" placeholder="مثال: شهادة صحية"></td>
                <td><input class="doc-name-ar-input" type="text" value="${escapeValue(info.name_ar || columnName)}" placeholder="الاسم الظاهر بالعربية"></td>
                <td><input class="doc-name-en-input" type="text" value="${escapeValue(info.name_en || '')}" placeholder="English Name" dir="ltr"></td>
                <td><input class="doc-code-input" type="text" value="${escapeValue(info.code || '')}" placeholder="HC" dir="ltr"></td>
                <td><input style="width:70px;" class="doc-order-input" type="number" min="1" value="${escapeValue(order)}"></td>
                <td class="doc-required-cell"><input class="doc-required-input" type="checkbox" ${info.required !== false ? 'checked' : ''}></td>
                <td><button type="button" class="btn-remove-doc" onclick="this.closest('tr').remove()">حذف</button></td>
            </tr>`);
    }

    async function loadDocTypes() {
        const status = document.getElementById('editorStatus');
        status.className = 'status-msg';
        status.textContent = '⏳ جاري تحميل الثوابت...';
        try {
            const response = await fetch('/api/constants-data');
            const data = await response.json();
            const types = data.document_types || {};
            const entries = Object.entries(types);
            
            document.getElementById('docTypesRows').innerHTML = '';
            if (entries.length === 0) {
                addDocTypeRow();
            } else {
                entries.sort((a, b) => (Number(a[1].order) || 999) - (Number(b[1].order) || 999))
                       .forEach(([column, info]) => addDocTypeRow(column, info));
            }
            status.textContent = '';
        } catch (error) {
            status.className = 'status-msg status-error';
            status.textContent = '❌ تعذر تحميل البيانات.';
        }
    }

    async function saveDocTypesEditor() {
        const status = document.getElementById('editorStatus');
        const documentTypes = {};
        const rows = [...document.querySelectorAll('#docTypesRows tr')];
        
        // مجموعة فريدة لمنع تكرار الرموز أثناء الإدخال في الشاشة
        const usedCodes = new Set();
        
        try {
            if (!rows.length) throw new Error('أضف نوع وثيقة واحدًا على الأقل.');
            for(let row of rows) {
                const column = row.querySelector('.doc-column-input').value.trim();
                const nameAr = row.querySelector('.doc-name-ar-input').value.trim();
                const nameEn = row.querySelector('.doc-name-en-input').value.trim();
                const code = row.querySelector('.doc-code-input').value.trim().toUpperCase();
                const order = Number(row.querySelector('.doc-order-input').value) || 1;
                const required = row.querySelector('.doc-required-input').checked;
                
                if (!column || !nameAr) throw new Error('أدخل الاسم الداخلي والاسم بالعربية لكل وثيقة.');
                if (!code) throw new Error(`يرجى إدخال الرمز الخاص (Code) للوثيقة: "${nameAr}" لأنه حقل إلزامي وفريد.`);
                
                if (documentTypes[column]) throw new Error(`الاسم الداخلي مكرر: ${column}`);
                
                // 🛑 فحص حظر تكرار الرمز الخاص (Code) في الواجهة
                if (usedCodes.has(code)) {
                    throw new Error(`الرمز الخاص (Code) مكرر: "${code}". يجب أن يكون لكل نوع وثيقة رمز فريد وخاص بها.`);
                }
                usedCodes.add(code);
                
                documentTypes[column] = { name_ar: nameAr, name_en: nameEn, code, required, order };
            }
        } catch (error) {
            status.className = 'status-msg status-error';
            status.textContent = '⚠️ ' + error.message;
            return;
        }

        status.className = 'status-msg';
        status.textContent = '⏳ جاري الحفظ وتحديث الثوابت...';
        try {
            const response = await fetch('/api/constants-data', {
                method: 'PUT',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({document_types: documentTypes})
            });
            const data = await response.json();
            if (response.ok && data.status === 'ok') {
                status.className = 'status-msg status-ok';
                status.textContent = '✅ تم حفظ التعديلات محلياً بنجاح! اضغط الآن على زر المزامنة لتطبيقها بالإكسل.';
            } else {
                status.className = 'status-msg status-error';
                status.textContent = '❌ ' + (data.message || 'فشل حفظ التعديلات.');
            }
        } catch (error) {
            status.className = 'status-msg status-error';
            status.textContent = '❌ فشل حفظ التعديلات بسبب خطأ في الشبكة.';
        }
    }

    async function syncColumnsFromConstants() {
        const status = document.getElementById('editorStatus');
        status.className = 'status-msg';
        status.textContent = '⏳ جاري فحص ملف الإكسل والمزامنة الشاملة...';
        
        const allowDelete = document.getElementById('allowDeleteCheckbox').checked;
        
        try {
            const r = await fetch('/api/constants/sync-columns', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ allow_delete: allowDelete })
            });
            const d = await r.json();
            if (d.status === 'ok') {
                status.className = 'status-msg status-ok';
                status.textContent = '✅ ' + d.message;
            } else {
                status.className = d.status === 'warning' ? 'status-msg status-warn' : 'status-msg status-error';
                status.textContent = '⚠️ ' + d.message;
            }
        } catch (e) {
            status.className = 'status-msg status-error';
            status.textContent = '❌ خطأ في الاتصال بالسيرفر أثناء المزامنة.';
        }
    }
</script>
</body>
</html>
"""

def init_constants_routes(base_dir):
    config_manager = ConfigManager(base_dir)
    doc_manager = DocTypeManager(base_dir)
    repo = ExcelRepository(config_manager)

    @constants_bp.route('/Doc_Type')
    def doc_type_screen():
        return render_template_string(CONSTANTS_TEMPLATE)

    @constants_bp.route('/api/constants-data', methods=['GET', 'PUT'])
    def handle_constants_data():
        if request.method == 'GET':
            doc_manager.data = doc_manager._load_or_create()
            return jsonify(doc_manager.data)
        else:
            data = request.get_json() or {}
            if 'document_types' not in data: 
                return jsonify({'status': 'error', 'message': 'بيانات غير مكتملة.'}), 400
            
            # 🔐 جدار حماية خلفي في البايثون (Backend Verification) لمنع التكرار مطلقاً
            fresh_types = data.get('document_types', {})
            backend_codes = set()
            for col_name, info in fresh_types.items():
                code = str(info.get('code', '')).strip().upper()
                if not code:
                    return jsonify({'status': 'error', 'message': f'الحقل (Code) مطلوب ولا يمكن تركه فارغاً للعمود {col_name}'}), 400
                if code in backend_codes:
                    return jsonify({'status': 'error', 'message': f'الرمز الخاص ({code}) مكرر في السيرفر! يجب استخدام رموز فريدة لكل وثيقة.'}), 400
                backend_codes.add(code)
            
            # حفظ التعديلات بأمان بعد تخطي الفحص بنجاح
            doc_manager.save_types(data)
            return jsonify({'status': 'ok'})

    @constants_bp.route('/api/constants/sync-columns', methods=['POST'])
    def sync_columns_from_constants_api():
        excel = repo.get_resolved_path()
        if not excel or not os.path.exists(excel):
            return jsonify({'status': 'error', 'message': 'مسار ملف الإكسل غير مححدد أو الملف غير موجود.'})
        if not repo.check_permission():
            return jsonify({'status': 'error', 'message': 'ملف الإكسل مفتوح حالياً في برنامج آخر، يرجى إغلاقه أولاً.'})
        
        try:
            req_data = request.get_json() or {}
            allow_delete = req_data.get('allow_delete', False)
            
            df = pd.read_excel(excel, sheet_name='Students', converters={'student_id': lambda x: '' if pd.isna(x) else str(x).strip()})
            df = repo.normalize_student_id_series(df)
            
            fresh_types = doc_manager._load_or_create().get('document_types', {})
            core_cols = ['student_id', 'full_name', 'college', 'status', 'enrollment_year', 'folder_path']
            
            for col_name, info in fresh_types.items():
                if col_name in df.columns:
                    req = info.get('required', True)
                    df[col_name] = df[col_name].fillna('').astype(str).str.strip()
                    if req:
                        df.loc[df[col_name] == '', col_name] = '✗'
                else:
                    df[col_name] = '✗' if info.get('required', True) else ''

            if allow_delete:
                extra_cols = [c for c in df.columns if c not in core_cols and c not in fresh_types]
                if extra_cols:
                    df.drop(columns=extra_cols, inplace=True)

            doc_types_rows = []
            for col_name, info in sorted(fresh_types.items(), key=lambda x: x[1].get('order', 999)):
                doc_types_rows.append({
                    'column_name': col_name,
                    'name_ar': info.get('name_ar', col_name),
                    'name_en': info.get('name_en', ''),
                    'code': info.get('code', '').upper(),
                    'required': 1 if info.get('required', True) else 0,
                    'order': info.get('order', 999)
                })
            
            new_dt_df = pd.DataFrame(doc_types_rows)

            with pd.ExcelWriter(excel, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Students', index=False)
                new_dt_df.to_excel(writer, sheet_name='DocumentTypes', index=False)
                
            return jsonify({'status': 'ok', 'message': 'تمت المزامنة وتحديث جدول الطلاب وجدول أنواع الوثائق (DocumentTypes) في الإكسل بنجاح ومطابقتها للشاشة.'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'فشلت المزامنة بسبب خطأ: {str(e)}'})

    return constants_bp