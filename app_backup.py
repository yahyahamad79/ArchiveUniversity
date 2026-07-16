import os
import json
from flask import Flask, render_template, request, jsonify

# الاستيراد النظيف والمباشر من مجلد الـ modules
from modules.excel_manager import load_excel_data
from modules.matcher import process_and_sync_archive

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
# شاشات عرض واجهات المستخدم
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
# APIs العمليات والخدمات الخلفية
# ==========================================
@app.route('/api/get-constants', methods=['GET'])
def get_constants():
    try:
        doc_types = load_doc_types()
        return jsonify({"success": True, "document_types": doc_types})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/load-data', methods=['POST'])
def load_data():
    data = request.json or {}
    excel_path = data.get('excel_path', '').strip()
    try:
        df = load_excel_data(excel_path)
        students = df.fillna("").to_dict(orient='records')
        return jsonify({"success": True, "students": students})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/sync', methods=['POST'])
def sync_archive():
    data = request.json or {}
    workspace_path = data.get('workspace_path', '').strip()
    archive_path = data.get('archive_path', '').strip()
    excel_path = data.get('excel_path', '').strip()

    if not all([workspace_path, archive_path, excel_path]):
        return jsonify({"success": False, "message": "الرجاء تحديد المسارات الثلاثة أولاً."}), 400

    try:
        doc_types = load_doc_types()
        # تشغيل الفحص الذكي عبر الـ matcher المستورد
        success, result = process_and_sync_archive(workspace_path, archive_path, excel_path, doc_types)
        
        if success:
            return jsonify({
                "success": True,
                "message": result["message"],
                "students": result["students"]
            })
        else:
            return jsonify({"success": False, "message": result}), 400
            
    except Exception as e:
        return jsonify({"success": False, "message": f"فشلت المزامنة والمعالجة: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)