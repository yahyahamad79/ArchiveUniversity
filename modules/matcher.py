import os
import shutil
# الاستيراد الصحيح ليتماشى مع تشغيل app.py من المجلد الرئيسي
from modules.excel_manager import load_excel_data, save_excel_data, find_student_by_filename

def determine_doc_type_from_filename(file_name, doc_types):
    """تحديد نوع الوثيقة بناءً على الرموز المكتوبة في اسم الملف (مثل 111_BC أو 222_ID)"""
    name_upper = file_name.upper()
    
    for doc_name, doc_info in doc_types.items():
        code = doc_info.get("code", "").upper()
        # نفحص وجود رمز الوثيقة مسبوقاً بشرطة سفلى أو شرطة عادية أو حتى ملتصقاً بالاسم
        if f"_{code}" in name_upper or f"-{code}" in name_upper or name_upper.endswith(f"{code}.JPEG") or name_upper.endswith(f"{code}.JPG") or name_upper.endswith(f"{code}.PNG"):
            return code
            
    # كخيار احتياطي إذا كان اسم الملف مجرد رقم (مثل 111.jpeg أو 222.jpeg) دون رمز وثيقة واضح:
    # سنقوم بفرض رمز افتراضي أو تركه للفحص يدوياً لمنع تداخل الملفات.
    return None

def process_and_sync_archive(workspace_path, archive_path, excel_path, doc_types):
    """
    الدورة الكاملة لمطابقة أسماء ملفات صندوق العمل المؤقت مع الإكسل
    """
    if not os.path.exists(workspace_path):
        return False, "مجلد العمل المؤقت غير موجود."
        
    df = load_excel_data(excel_path)
    files = os.listdir(workspace_path)
    processed_count = 0
    
    # تحديد المستندات المطلوبة لحساب نسب الإنجاز
    required_docs = [info["code"] for info in doc_types.values() if info.get("required") is True]
    total_required_count = len(required_docs) if required_docs else 1
    
    for file_name in files:
        file_path = os.path.join(workspace_path, file_name)
        if os.path.isdir(file_path):
            continue
            
        ext = os.path.splitext(file_name)[1].replace('.', '').lower()
        if ext not in ['jpg', 'jpeg', 'png']:
            continue
        
        # 1. تحديد نوع الوثيقة من اسم الملف
        doc_code = determine_doc_type_from_filename(file_name, doc_types)
        if not doc_code:
            # إذا لم نجد الرمز في الاسم، سنحاول معرفته من الكلمات الدلالية لاسم الملف نفسه لتسهيل المطابقة
            name_lower = file_name.lower()
            for doc_name, doc_info in doc_types.items():
                code = doc_info.get("code", "").upper()
                if code.lower() in name_lower:
                    doc_code = code
                    break
            
            if not doc_code:
                print(f"⚠️ الملف {file_name} لا يحتوي على رمز وثيقة صالح في اسمه.")
                continue
            
        # 2. مطابقة هوية الطالب من الأرقام أو الاسم الموجود في اسم الملف
        student_id = find_student_by_filename(df, file_name)
        
        if student_id:
            # معالجة الأصفار على اليسار للرقم الجامعي عند التسمية النهائية
            student_id_clean = str(student_id).strip()
            if len(student_id_clean) < 6 and student_id_clean.isdigit():
                student_id_clean = student_id_clean.zfill(6)

            # 3. نقل الملف إلى الأرشيف النهائي داخل مجلد الوثيقة المخصصة
            doc_info = next((info for info in doc_types.values() if info["code"].upper() == doc_code), None)
            if doc_info:
                storage_folder_name = doc_info["storage_path"].strip('/')
                target_folder = os.path.join(archive_path, storage_folder_name)
                
                if not os.path.exists(target_folder):
                    os.makedirs(target_folder)
                
                # الاسم الموحد والنظيف الجديد (الرقم الجامعي للطالب)
                new_file_name = f"{student_id_clean}.{ext}"
                target_file_path = os.path.join(target_folder, new_file_name)
                
                # نقل الملف الفعلي
                shutil.move(file_path, target_file_path)
                
                # 4. تحديث الإكسل باستخدام العمود الصحيح (ID أو رقم الهوية أو رقم الجلوس)
                matched_row_idx = None
                for col in ['ID', 'رقم الهوية', 'رقم الجلوس']:
                    if col not in df.columns:
                        continue
                    mask = df[col].astype(str).str.strip() == str(student_id).strip()
                    if mask.any():
                        matched_row_idx = df.index[mask][0]
                        break

                if matched_row_idx is not None:
                    df.at[matched_row_idx, doc_code] = "نعم"
                    processed_count += 1

    # 5. حساب نسب الاكتمال وحالة الملف الكلية
    def calculate_row_metrics(row):
        matched_required = sum(1 for doc in required_docs if row.get(doc) == "نعم")
        ratio = (matched_required / total_required_count) * 100
        row['نسبة الاكتمال'] = f"{int(ratio)}%"
        row['حالة الملف'] = "مكتمل" if ratio == 100 else "غير مكتمل"
        return row

    df = df.apply(calculate_row_metrics, axis=1)
    
    # حفظ الإكسل
    save_excel_data(df, excel_path)
    students_list = df.fillna("").to_dict(orient='records')
    
    return True, {
        "message": f"اكتملت المزامنة بنجاح! تم التعرف على {processed_count} ملفات وإعادة تنظيمها وتوزيعها داخل المجلدات.",
        "students": students_list
    }