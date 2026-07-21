import os
import json
import tempfile
from flask import Flask, render_template, request, jsonify
from document_extractor import extract_document_info, SUPPORTED_EXTENSIONS

app = Flask(__name__)

DB_DIR = 'database'
JSON_PATH = os.path.join(DB_DIR, 'doc_types.json')
PATHS_JSON_PATH = os.path.join(DB_DIR, 'paths.json')

def load_doc_types():
    if not os.path.exists(JSON_PATH):
        return {}
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get("document_types", {})
    except Exception:
        return {}

def load_paths():
    if not os.path.exists(PATHS_JSON_PATH):
        return {}
    try:
        with open(PATHS_JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get("paths", {})
    except Exception:
        return {}

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

# ==========================================
# APIs العمليات والخدمات الخلفية (الثوابت فقط)
# ==========================================
@app.route('/api/get-constants', methods=['GET'])
def get_constants():
    try:
        doc_types = load_doc_types()
        return jsonify({"success": True, "document_types": doc_types})
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

# ==========================================
# APIs مسارات العمل المشتركة (workspace / archive / excel)
# مصدر واحد للأسماء/الحالة يُقرأ من كل الشاشات (paths, matching)
# ملاحظة: هذا يخزّن الاسم/الوصف فقط وليس صلاحية وصول فعلية للملف —
# الوصول الفعلي (FileSystemHandle) يبقى مخزناً بالمتصفح (IndexedDB) فقط.
# ==========================================
@app.route('/api/get-paths', methods=['GET'])
def get_paths():
    try:
        paths = load_paths()
        return jsonify({"success": True, "paths": paths})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/save-paths', methods=['POST'])
def save_paths():
    data = request.json or {}
    incoming = data.get('paths', {})

    try:
        if not os.path.exists(DB_DIR):
            os.makedirs(DB_DIR)

        # دمج مع البيانات الموجودة بدل الاستبدال الكامل، حتى لو حدّثت شاشة
        # واحد فقط من المسارات الثلاثة لا تُفقد بيانات الشاشات الأخرى
        current = load_paths()
        current.update(incoming)

        with open(PATHS_JSON_PATH, 'w', encoding='utf-8') as f:
            json.dump({"paths": current}, f, ensure_ascii=False, indent=4)

        return jsonify({"success": True, "message": "تم حفظ المسار بنجاح!", "paths": current})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

# ==========================================
# API استخراج الاسم ونوع الوثيقة محلياً (PaddleOCR + قواعد نصية)
# يعمل بالكامل دون إنترنت — الملف يُحفظ مؤقتاً ثم يُحذف فوراً بعد المعالجة
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

        doc_types = load_doc_types()
        result = extract_document_info(tmp_path, doc_types)
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
    