import os
import re

try:
    import easyocr
    # تهيئة القارئ لقراءة العربية والإنجليزية
    reader = easyocr.Reader(['ar', 'en'], gpu=False)
except ImportError:
    reader = None
    print("⚠️ تحذير: مكتبة EasyOCR غير مثبتة.")

def clean_arabic_text(text):
    """
    تطهير وتوحيد النصوص العربية لرفع دقة المطابقة وتجاوز أخطاء الـ OCR الشائعة
    """
    if not text:
        return ""
    n = str(text).strip().lower()
    # توحيد أشكال الألف
    n = re.sub(r'[أإآ]', 'ا', n)
    # توحيد التاء المربوطة والهاء في نهاية الكلمة
    n = re.sub(r'ة\b', 'ه', n)
    # توحيد الياء والألف المقصورة
    n = re.sub(r'ى\b', 'ي', n)
    # إزالة التشكيل والرموز الزائدة والمحافظة على الحروف والأرقام
    n = re.sub(r'[\u064b-\u0652]', '', n)
    # تقليص المسافات المتكررة لمسافة واحدة
    n = re.sub(r'\s+', ' ', n)
    return n.strip()

def extract_text_from_image(image_path):
    """قراءة الصورة واستخراج النصوص منها بالكامل"""
    if not os.path.exists(image_path):
        return ""
    
    if reader is not None:
        try:
            results = reader.readtext(image_path, detail=0)
            return " ".join(results)
        except Exception as e:
            print(f"❌ خطأ أثناء قراءة الـ OCR للملف {image_path}: {str(e)}")
            return ""
    else:
        # نظام محاكاة في حال عدم توفر المكتبة
        base_name = os.path.basename(image_path)
        return base_name.replace("_", " ").replace("-", " ")

def determine_document_type(extracted_text, doc_types):
    """
    تحديد نوع الوثيقة بمطابقة النص المستخرج مع الكلمات الدلالية
    الموجودة في ملف الثوابت (JSON) بعد التطهير
    """
    cleaned_text = clean_arabic_text(extracted_text)
    
    for doc_name, doc_info in doc_types.items():
        keywords = doc_info.get("ocr_keywords", [])
        code = doc_info.get("code", "").upper()
        
        for keyword in keywords:
            cleaned_keyword = clean_arabic_text(keyword)
            if cleaned_keyword and cleaned_keyword in cleaned_text:
                return code # إرجاع رمز الوثيقة مثل BC
                
    return None