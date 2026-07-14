import os
import json
from flask import Flask, render_template, request, jsonify
import pandas as pd

app = Flask(__name__)

# دالة لقراءة ملف الثوابت doc_types.json ديناميكياً
def load_doc_types():
    json_path = os.path.join('database', 'doc_types.json')
    if not os.path.exists(json_path):
        return {}
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f).get("document_types", {})

@app.route('/')
def index():
    # عرض الصفحة الرئيسية
    return render_template('index.html')

@app.route('/api/load-data', methods=['POST'])
def load_data():
    """تحميل سجلات الطلاب من ملف الإكسل المختار ديناميكياً"""
    data = request.json
    excel_path = data.get('excel_path')

    if not excel_path or not os.path.exists(excel_path):
        return jsonify({"success": False, "message": "مسار ملف الإكسل غير صحيح أو غير موجود."}), 400

    try:
        # قراءة الحقل ID بشكل نص صارم لمنع سقوط الأصفار
        df = pd.read_excel(excel_path, dtype={'ID': str})
        
        # استبدال قيم NaN بقيم نصية فارغة لضمان توافق JSON
        df = df.fillna("")
        
        students = df.to_dict(orient='records')
        return jsonify({"success": True, "students": students})
    except Exception as e:
        return jsonify({"success": False, "message": f"حدث خطأ أثناء قراءة الملف: {str(e)}"}), 500

@app.route('/api/sync', methods=['POST'])
def sync_archive():
    """بروتوكول المطابقة والمزامنة الآمنة للمسارات الثلاثة"""
    data = request.json
    workspace_path = data.get('workspace_path') # صندوق ملفات العمل
    archive_path = data.get('archive_path')     # الأرشيف النهائي storage_secure
    excel_path = data.get('excel_path')         # ملف الإكسل

    # التحقق من وجود المسارات محلياً
    if not all([workspace_path, archive_path, excel_path]):
        return jsonify({"success": False, "message": "يرجى تحديد جميع المسارات الثلاثة أولاً."}), 400
    
    if not os.path.exists(archive_path) or not os.path.exists(excel_path):
        return jsonify({"success": False, "message": "مسار الأرشيف أو ملف الإكسل غير موجود محلياً."}), 400

    try:
        doc_types = load_doc_types()
        required_docs = [info["code"] for info in doc_types.values() if info.get("required") == True]
        total_required_count = len(required_docs)

        # قراءة الإكسل مع الاحتفاظ بالـ ID كنص
        df = pd.read_excel(excel_path, dtype={'ID': str})

        # 1. مطابقة المجلدات المحلية الآمنة وتحديث الإكسل
        for doc_name, doc_info in doc_types.items():
            doc_code = doc_info["code"]
            storage_folder_name = doc_info["storage_path"].strip('/')
            allowed_exts = [ext.lower() for ext in doc_info["allowed_extensions"]]

            # المسار المطلق للمجلد الرمزي للوثيقة داخل الأرشيف النهائي
            target_folder = os.path.join(archive_path, storage_folder_name)

            # إنشاء المجلد تلقائياً إذا لم يكن موجوداً (بأمان دون تعديل الملفات القديمة)
            if not os.path.exists(target_folder):
                os.makedirs(target_folder)

            # جلب أسماء الملفات بدون الامتداد
            existing_files = os.listdir(target_folder)
            valid_ids = set()
            for f in existing_files:
                name, ext = os.path.splitext(f)
                if ext.replace('.', '').lower() in allowed_exts:
                    valid_ids.add(name.strip())

            # تحديث العمود في الإكسل بناءً على الوجود الفعلي للملف
            df[doc_code] = df['ID'].apply(lambda student_id: "نعم" if str(student_id).strip() in valid_ids else "لا")

        # 2. حساب نسبة الاكتمال وحالة الملف
        def update_metrics(row):
            matched_required = sum(1 for doc in required_docs if row.get(doc) == "نعم")
            ratio = (matched_required / total_required_count) * 100
            row['نسبة الاكتمال'] = f"{int(ratio)}%"
            row['حالة الملف'] = "مكتمل" if ratio == 100 else "غير مكتمل"
            return row

        df = df.apply(update_metrics, axis=1)

        # حفظ التعديلات بأمان كامل محلياً دون لمس أي ملفات حقيقية
        df.to_excel(excel_path, index=False)
        
        # تحويل البيانات إلى قاموس لإرسالها للواجهة فوراً بعد التحديث
        updated_students = df.fillna("").to_dict(orient='records')

        return jsonify({
            "success": True, 
            "message": "تمت المطابقة وتحديث السجلات بنجاح وبأمان تام.",
            "students": updated_students
        })

    except Exception as e:
        return jsonify({"success": False, "message": f"فشلت المزامنة: {str(e)}"}), 500

if __name__ == '__main__':
    # تشغيل الخادم المحلي على المنفذ 5000
    app.run(debug=True, port=5000)