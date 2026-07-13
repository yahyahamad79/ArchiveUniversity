import os
import json
import pandas as pd

def run_archive_sync(storage_secure_path, json_config_path, excel_db_path):
    """
    بروتوكول المطابقة والمزامنة الآمنة للنظام المزدوج.
    جميع المسارات تُمرر ديناميكياً من خلال الواجهة ولا توجد مسارات ثابتة.
    """
    # 1. التحقق من وجود المجلدات والملفات الممررة ديناميكياً
    if not os.path.exists(storage_secure_path):
        raise FileNotFoundError(f"مجلد التخزين المحدّد غير موجود: {storage_secure_path}")
    if not os.path.exists(json_config_path):
        raise FileNotFoundError(f"ملف الثوابت json غير موجود في المسار: {json_config_path}")
    if not os.path.exists(excel_db_path):
        raise FileNotFoundError(f"ملف قاعدة البيانات الإكسل غير موجود: {excel_db_path}")

    # 2. قراءة ملف الثوابت المطور doc_types.json
    with open(json_config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    doc_types = config_data.get("document_types", {})

    # 3. قراءة ملف الإكسل مع إجبار حقل ID على أن يكون نصاً (String) لحفظ الأصفار
    df = pd.read_excel(excel_db_path, dtype={'ID': str})

    # تقسيم الوثائق إلى إلزامية واختيارية بناءً على ملف الـ JSON
    required_docs = [info["code"] for info in doc_types.values() if info.get("required") == True]
    total_required_count = len(required_docs)

    # 4. بدء عملية الفحص والمطابقة لكل وثيقة معرفة في الـ JSON
    for doc_name, doc_info in doc_types.items():
        doc_code = doc_info["code"]           # مثل: HS, BC, ID
        storage_path = doc_info["storage_path"].strip('/') # المجلد الرمزي للوثيقة
        allowed_exts = [ext.lower() for ext in doc_info["allowed_extensions"]] # الامتدادات المعتمدة

        # بناء المسار المطلق للمجلد الرمزي للوثيقة بشكل ديناميكي كامل
        target_folder = os.path.join(storage_secure_path, storage_path)

        # إذا كان المجلد الرمزي غير موجود محلياً، يتم إنشاؤه بأمان دون المساس بالملفات الأخرى
        if not os.path.exists(target_folder):
            os.makedirs(target_folder)

        # قراءة قائمة الملفات الفعلية الموجودة داخل المجلد الرمزي
        existing_files = os.listdir(target_folder)

        # بناء قاموس سريع للملفات المتاحة لتسريع عملية البحث والتطابق الفردي
        # الفكرة: استخراج اسم الملف بدون الامتداد إذا كان امتداده معتمداً في الـ JSON
        valid_files_in_folder = set()
        for f in existing_files:
            name, ext = os.path.splitext(f)
            if ext.replace('.', '').lower() in allowed_exts:
                valid_files_in_folder.add(name) # إضافة الرقم الجامعي المستخرج كنص

        # 5. مطابقة سجلات الطلاب في الإكسل مع الملفات الفعلية في المجلد الرمزي
        # يتم تحديث العمود الخاص بالوثيقة بـ "نعم" أو "لا"
        df[doc_code] = df['ID'].apply(lambda student_id: "نعم" if str(student_id).strip() in valid_files_in_folder else "لا")

    # 6. الحساب الديناميكي لنسبة الاكتمال وحالة الملف بناءً على الشروط الصارمة
    # نسبة الاكتمال تعتمد على الوثائق الإلزامية فقط (5 وثائق حالياً)
    def calculate_metrics(row):
        # حساب كم وثيقة إلزامية يمتلكها الطالب حالياً في المجلدات
        matched_required = sum(1 for doc in required_docs if row.get(doc) == "نعم")
        
        # حساب النسبة المئوية
        completion_ratio = (matched_required / total_required_count) * 100
        row['نسبة الاكتمال'] = f"{int(completion_ratio)}%"
        
        # تحديد حالة الملف الصارمة
        if completion_ratio == 100:
            row['حالة الملف'] = "مكتمل"
        else:
            row['حالة الملف'] = "غير مكتمل"
        return row

    # تطبيق معادلة الاحتساب على كل السجلات
    df = df.apply(calculate_metrics, axis=1)

    # 7. حفظ التحديثات في ملف الإكسل نفسه بأمان وبدون أي تدمير للبيانات القديمة
    df.to_excel(excel_db_path, index=False)
    print("» تمت عملية الفحص والاعتماد بنجاح وتحديث قاعدة البيانات المحلية الآمنة.")

# --- مثال على كيفية استدعاء الدالة ديناميكياً من واجهة المستخدم (تطبيق سطح مكتب أو ويب) ---
if __name__ == "__main__":
    # في التطبيق الفعلي، هذه المسارات تأتي ديناميكياً من الـ File Picker الخاص بالواجهة
    # الموظف يختار مجلد التخزين الخارجي المنفصل ومسار ملفاته لمرة واحدة
    
    USER_SELECTED_STORAGE = r"E:\Archiving_System_Storage\storage_secure" # مسار المجلد الخارجي المنفصل
    PROJECT_ROOT_JSON = "doc_types.json"                                  # مجلد التطبيق الحالي
    PROJECT_DATABASE_EXCEL = "students_db.xlsx"                           # مسار ملف الإكسل الحالي
    
    # تشغيل المعالج الديناميكي
    try:
        run_archive_sync(
            storage_secure_path=USER_SELECTED_STORAGE,
            json_config_path=PROJECT_ROOT_JSON,
            excel_db_path=PROJECT_DATABASE_EXCEL
        )
    except Exception as e:
        print(f"خطأ أثناء المزامنة: {e}")