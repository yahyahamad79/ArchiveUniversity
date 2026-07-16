import os
import pandas as pd
import re

def load_excel_data(excel_path):
    """تحميل ملف الإكسل الرئيسي مع الحفاظ على الأصفار في الأعمدة الحساسة"""
    if not os.path.exists(excel_path):
        raise FileNotFoundError("ملف قاعدة البيانات غير موجود.")
    
    df = pd.read_excel(excel_path, dtype={
        'ID': str, 
        'رقم الهوية': str, 
        'رقم الجلوس': str
    })
    
    for col in ['ID', 'رقم الهوية', 'رقم الجلوس']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
            
    return df

def save_excel_data(df, excel_path):
    """حفظ التعديلات في ملف الإكسل"""
    df.to_excel(excel_path, index=False)

def normalize_arabic(s):
    """
    تطهير وتوحيد النص العربي بناءً على دالة normalizeArabic في ملف CompareStud.html حرفياً 100%:
    """
    if s is None or pd.isna(s):
        return ""
    
    s = str(s).strip()
    
    # 1. إزالة التشكيل والتطويل (كشيدة)
    s = re.sub(r'[\u064B-\u0652\u0670\u0640]', '', s)
    
    # 2. توحيد كل أشكال الألف والهمزة إلى ألف عادية (إ أ آ ا ٱ)
    s = re.sub(r'[إأآاٱ]', 'ا', s)
    
    # 3. حذف الهمزة المنفردة وعلى الواو والياء (ء ؤ ئ) تماماً
    s = re.sub(r'[ؤئء]', '', s)
    
    # 4. التاء المربوطة = هاء
    s = s.replace('ة', 'ه')
    
    # 5. الألف المقصورة = ياء
    s = s.replace('ى', 'ي')
    
    # 6. توحيد الياء
    s = s.replace('ي', 'ي')
    
    # 7. إزالة أي محرف غير الحروف العربية الأساسية (حذف المسافات، الأرقام والرموز)
    s = re.sub(r'[^\u0621-\u064A]', '', s)
    
    return s

def calculate_similarity(a, b):
    """
    حساب نسبة التشابه التقريبي بناءً على دالة similarity (مسافة ليفنشتاين) في ملف CompareStud.html:
    """
    if a == b:
        return 1.0
    if not a or not b:
        return 0.0
        
    m, n = len(a), len(b)
    
    # إنشاء مصفوفة المسافات (DP Table)
    d = [[0] * (n + 1) for _ in range(m + 1)]
    
    for i in range(m + 1):
        d[i][0] = i
    for j in range(n + 1):
        d[0][j] = j
        
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(
                d[i - 1][j] + 1,      # Deletion
                d[i][j - 1] + 1,      # Insertion
                d[i - 1][j - 1] + cost # Substitution
            )
            
    return 1.0 - (d[m][n] / max(m, n))


def _get_student_id_value(row):
    """إرجاع قيمة الهوية من الصف إذا وجدت."""
    for col in ['ID', 'رقم الهوية', 'رقم الجلوس']:
        if col in row.index:
            value = row[col]
            if value is not None and not pd.isna(value):
                text = str(value).strip()
                if text:
                    return text
    return None


def find_student_by_filename(df, file_name):
    """
    البحث عن الطالب من اسم الملف باستخدام نفس المنطق في CompareStud.html:
    1) مطابقة رقمية من الأرقام الموجودة في اسم الملف.
    2) مطابقة اسمية عربية بعد التطبيع.
    3) مطابقة تقريبية عند الحاجة.
    """
    if df is None or df.empty:
        return None

    stem = os.path.splitext(file_name)[0]
    digits = re.findall(r'\d+', stem)

    # 1) محاولة المطابقة الرقمية (الأرقام في اسم الملف)
    if digits:
        for raw_num in digits:
            for col in ['ID', 'رقم الهوية', 'رقم الجلوس']:
                if col not in df.columns:
                    continue
                matches = df[df[col].astype(str).str.strip() == raw_num.strip()]
                if not matches.empty:
                    return _get_student_id_value(matches.iloc[0])

    # 2) محاولة المطابقة الاسمية بعد التطبيع
    # استخدام الاسم الكامل من اسم الملف (بدون الامتداد والأرقام) حتى يتطابق مع أسماء مثل: عبد الله محمد
    base_name = re.sub(r'\d+', '', stem)
    base_name = base_name.replace('-', ' ').replace('_', ' ').strip()

    if not base_name:
        return None

    normalized_query = normalize_arabic(base_name)
    if not normalized_query:
        return None

    name_columns = []
    for col in df.columns:
        if isinstance(col, str) and re.search(r'(اسم|name|student|full)', col, re.IGNORECASE):
            name_columns.append(col)

    if not name_columns:
        return None

    best_score = 0.0
    best_match = None

    for col in name_columns:
        for _, row in df.iterrows():
            raw_value = row[col]
            if raw_value is None or pd.isna(raw_value):
                continue
            normalized_value = normalize_arabic(raw_value)
            if not normalized_value:
                continue

            if normalized_value == normalized_query:
                return _get_student_id_value(row)

            score = calculate_similarity(normalized_query, normalized_value)
            if score > best_score:
                best_score = score
                best_match = row

    if best_match is not None and best_score >= 0.85:
        return _get_student_id_value(best_match)

    return None


def create_temp_files_excel(workspace_path):
    """
    قراءة مجلد الصندوق وبناء جدول بأسماء الملفات لتسهيل المقارنة
    """
    if not os.path.exists(workspace_path):
        return None
        
    files = os.listdir(workspace_path)
    records = []
    
    for file_name in files:
        ext = os.path.splitext(file_name)[1].replace('.', '').lower()
        if ext in ['jpg', 'jpeg', 'png']:
            name_without_ext = os.path.splitext(file_name)[0]
            # فصل اللواحق الإضافية مثل _ID أو _BC إن وُجدت
            clean_name = re.split(r'[-_]', name_without_ext)[0].strip()
            
            records.append({
                'Original_Filename': file_name,
                'Clean_Name': clean_name,
                'Extension': ext
            })
            
    return pd.DataFrame(records)