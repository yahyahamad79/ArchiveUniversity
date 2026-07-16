import os
import json
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

DB_DIR = 'database'
JSON_PATH = os.path.join(DB_DIR, 'doc_types.json')

def load_doc_types():
    if not os.path.exists(JSON_PATH):
        return {}
    try:
        with open(JSON_PATH, 'r', encoding='utf-8') as f:
            return json.load(f).get("document_types", {})
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    