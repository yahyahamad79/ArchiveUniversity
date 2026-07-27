import os
import json
import tempfile
import io
import zipfile
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
from document_extractor import extract_document_info, SUPPORTED_EXTENSIONS

app = Flask(__name__)

DB_DIR = 'database'
JSON_PATH = os.path.join(DB_DIR, 'doc_types.json')
PATHS_JSON_PATH = os.path.join(DB_DIR, 'paths.json')

def load_doc_types():
    return load_full_doc_types_file().get("document_types", {})

# الملف الكامل يتضمن الآن "document_types" و"ignored_codes" (الرموز المحذوفة
# صراحة من الشاشة — تُستبعد من "مزامنة شاملة" حتى لا تُعاد من مجلدها الفعلي
# تلقائياً، مع بقاء المجلد نفسه دون أي حذف أو لمس)
def load_full_doc_types_file():
    if not os.path.exists(JSON_PATH):
        return {"document_types": {}, "ignored_codes": []}
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.setdefault("document_types", {})
            data.setdefault("ignored_codes", [])
            return data
    except Exception:
        return {"document_types": {}, "ignored_codes": []}

def save_full_doc_types_file(data):
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_paths_file():
    if not os.path.exists(PATHS_JSON_PATH):
        return {"workspaces": {}}
    try:
        with open(PATHS_JSON_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if "workspaces" not in data:
            # ترقية تلقائية لمرة واحدة من الصيغة القديمة (مشتركة بلا مستخدمين)
            # — البيانات القديمة تُنسخ لمساحة عمل باسم "default" حتى لا تُفقد
            legacy = data.get("paths", {})
            data = {"workspaces": {"default": legacy}} if legacy else {"workspaces": {}}
        return data
    except Exception:
        return {"workspaces": {}}

def save_paths_file(data):
    if not os.path.exists(DB_DIR):
        os.makedirs(DB_DIR)
    with open(PATHS_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# ==========================================
# شاشات عرض واجهات المستخدم (توجيه الشاشات الفرعية)
# ==========================================
@app.route('/')
def index_screen():
    return render_template('index.html')

@app.route('/paths')
def paths_screen():
    return render_template('paths.html')

@app.route('/constants')
def constants_screen():
    return render_template('constants.html')

@app.route('/matching')
def matching_screen():
    return render_template('matching.html')

@app.route('/documents-check')
def documents_check_screen():
    return render_template('documents_check.html')

@app.route('/completion-tracking')
def completion_tracking_screen():
    return render_template('completion_tracking.html')

# ==========================================
# APIs العمليات والخدمات الخلفية (الثوابت فقط)
# ==========================================
@app.route('/api/get-constants', methods=['GET'])
def get_constants():
    try:
        full = load_full_doc_types_file()
        return jsonify({
            "success": True,
            "document_types": full.get("document_types", {}),
            "ignored_codes": full.get("ignored_codes", [])
        })
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/save-constants', methods=['POST'])
def save_constants():
    data = request.json or {}
    document_types = data.get('document_types', {})
    
    try:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)
            
        # حفظ البيانات كملف JSON مستقل دون الحاجة لمكتبات خارجية
        with open(JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump({"document_types": document_types}, f, ensure_ascii=False, indent=4)
            
        return jsonify({"success": True, "message": "تم حفظ الثوابت والمستندات بنجاح!"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# حفظ/تعديل نوع وثيقة واحد فقط — هذا ما تستدعيه فعلياً شاشة constants.html
# (original_name: المفتاح القديم عند التعديل، doc_key: المفتاح الجديد، doc_data: بيانات النوع)
@app.route('/api/save-constant', methods=['POST'])
def save_constant():
    data = request.json or {}
    original_name = (data.get('original_name') or '').strip()
    doc_key = (data.get('doc_key') or '').strip()
    doc_data = data.get('doc_data', {})

    if not doc_key:
        return jsonify({"success": False, "message": "اسم الوثيقة بالعربية مطلوب"}), 400

    try:
        full = load_full_doc_types_file()
        doc_types = full.get("document_types", {})
        ignored_codes = full.get("ignored_codes", [])

        # تعديل مع تغيير الاسم العربي (المفتاح) → احذف المفتاح القديم أولاً
        if original_name and original_name != doc_key and original_name in doc_types:
            del doc_types[original_name]

        doc_types[doc_key] = doc_data

        # المستخدم أعاد إنشاء/تعديل هذا النوع صراحة الآن — أزل رمزه من قائمة
        # "المتجاهَلة" إن كان مدرجاً فيها، حتى تتعامل معه "مزامنة شاملة" بشكل طبيعي مجدداً
        code = (doc_data.get('code') or '').strip().upper()
        if code and code in ignored_codes:
            ignored_codes = [c for c in ignored_codes if c != code]

        full["document_types"] = doc_types
        full["ignored_codes"] = ignored_codes
        save_full_doc_types_file(full)

        return jsonify({"success": True, "message": f'تم حفظ الوثيقة "{doc_key}" بنجاح!'})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# حذف نوع وثيقة واحد بالمفتاح (الاسم العربي)
@app.route('/api/delete-constant', methods=['POST'])
def delete_constant():
    data = request.json or {}
    doc_key = (data.get('doc_key') or '').strip()

    if not doc_key:
        return jsonify({"success": False, "message": "لم يُحدَّد مفتاح الوثيقة المطلوب حذفها"}), 400

    try:
        full = load_full_doc_types_file()
        doc_types = full.get("document_types", {})
        ignored_codes = full.get("ignored_codes", [])

        if doc_key not in doc_types:
            return jsonify({"success": False, "message": f'الوثيقة "{doc_key}" غير موجودة أصلاً'}), 404

        deleted_code = (doc_types[doc_key].get('code') or '').strip().upper()
        del doc_types[doc_key]

        # تسجيل الرمز كـ"متجاهَل" حتى لا تُعيد "مزامنة شاملة" إنشاءه تلقائياً من
        # مجلده الفعلي — المجلد نفسه يبقى كما هو تماماً، بلا حذف أو لمس
        if deleted_code and deleted_code not in ignored_codes:
            ignored_codes.append(deleted_code)

        full["document_types"] = doc_types
        full["ignored_codes"] = ignored_codes
        save_full_doc_types_file(full)

        return jsonify({"success": True, "message": f'تم حذف الوثيقة "{doc_key}" بنجاح!', "deleted_code": deleted_code})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# APIs مسارات العمل المشتركة (workspace / archive / excel)
# مصدر واحد للأسماء/الحالة يُقرأ من كل الشاشات (paths, matching)
# ملاحظة: هذا يخزّن الاسم/الوصف فقط وليس صلاحية وصول فعلية للملف —
# الوصول الفعلي (FileSystemHandle) يبقى مخزناً بالمتصفح (IndexedDB) فقط.
# ==========================================
@app.route('/api/get-paths', methods=['GET'])
def get_paths():
    try:
        username = (request.args.get('user') or '').strip() or 'default'
        data = load_paths_file()
        workspace = data.get('workspaces', {}).get(username, {})
        return jsonify({"success": True, "paths": workspace})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/save-paths', methods=['POST'])
def save_paths():
    body = request.json or {}
    username = (body.get('user') or '').strip() or 'default'
    incoming = body.get('paths', {})

    try:
        data = load_paths_file()
        data.setdefault('workspaces', {})

        # دمج مع البيانات الموجودة *لنفس مساحة العمل* بدل الاستبدال الكامل،
        # حتى لو حدّثت شاشة واحدة فقط من المسارات الثلاثة لا تُفقد بيانات
        # الشاشات الأخرى — وبدون أي تأثير على مساحات عمل المستخدمين الآخرين
        current = data['workspaces'].get(username, {})
        current.update(incoming)
        data['workspaces'][username] = current

        save_paths_file(data)

        return jsonify({"success": True, "message": "تم حفظ المسار بنجاح!", "paths": current})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# API تنزيل نسخة احتياطية (doc_types.json + paths.json) كملف ZIP واحد —
# بديل مجاني لقرص Render الدائم المدفوع: المستخدم ينزّل الملفين يدوياً
# ويرفعهما على GitHub بنفسه قبل أي نشر جديد، حتى لا تُفقد التعديلات على
# قرص Render المؤقت (ephemeral) عند إعادة النشر أو إعادة التشغيل
# ==========================================
@app.route('/api/download-backup', methods=['GET'])
def download_backup():
    try:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            if os.path.exists(JSON_PATH):
                zf.write(JSON_PATH, arcname='doc_types.json')
            if os.path.exists(PATHS_JSON_PATH):
                zf.write(PATHS_JSON_PATH, arcname='paths.json')
        buf.seek(0)

        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M')
        return send_file(
            buf,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'archive_backup_{timestamp}.zip'
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# API استخراج الاسم ونوع الوثيقة عبر Gemini Vision (سحابي)
# الملف يُحفظ مؤقتاً على القرص ثم يُحذف فوراً بعد المعالجة
# ==========================================
@app.route('/api/extract-document-info', methods=['POST'])
def extract_document_info_route():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "لم يتم إرفاق ملف"}), 400

    file = request.files['file']
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        return jsonify({"success": False, "message": f"نوع الملف غير مدعوم: {ext}"}), 400

    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=ext)
        os.close(fd)
        file.save(tmp_path)

        # مفتاح Gemini شخصي اختياري يبعته المستخدم من متصفحه (محفوظ محلياً
        # عنده فقط في شاشة "تهيئة مسارات النظام") — لا يُحفظ هنا في أي ملف
        # على الخادم، يُستخدم فقط لتنفيذ هذا الطلب ثم يُنسى فوراً
        personal_api_key = (request.form.get('gemini_api_key') or '').strip() or None

        doc_types = load_doc_types()
        result = extract_document_info(tmp_path, doc_types, api_key=personal_api_key)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    