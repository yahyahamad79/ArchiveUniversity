"""
document_extractor.py — استخراج الاسم العربي ونوع الوثيقة عبر Gemini Flash (سحابي، مجاني)
============================================================================================
⚠️ يرسل صورة الوثيقة فعلياً إلى Google Gemini API عبر الإنترنت. يتطلب:
  - متغيّر بيئة GEMINI_API_KEY مضبوطاً على الجهاز (مفتاح مجاني من aistudio.google.com،
    بدون بطاقة ائتمان — ضمن حدود الاستخدام اليومي المجاني لنموذج Flash)
  - اتصال إنترنت وقت الاستخراج فقط (وليس طوال تشغيل النظام)

قواعد تنظيف الاسم (إزالة الألقاب، توحيد الأسماء المركّبة، تنظيف المسافات)
هي نفسها المعتمدة سابقاً في مهارة arabic-name-ocr — بلا تغيير.

الاستخدام:
    from document_extractor import extract_document_info
    result = extract_document_info("student_id.jpg", doc_types_dict)
    print(result["name"], result["doc_type"])
"""

import re
import subprocess
import tempfile
from pathlib import Path

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}

# =========================================================
# قواعد تنظيف الاسم — منقولة كما هي من arabic-name-ocr/scripts/ocr_engine.py
# =========================================================
TITLES_TO_REMOVE = [
    "د.", "دكتور", "دكتورة", "الدكتور", "الدكتورة",
    "أ.", "أ.د.", "أستاذ", "أستاذة", "الأستاذ", "الأستاذة",
    "م.", "مهندس", "مهندسة",
    "سيد", "السيد", "الشيخ", "شيخ",
    "الحاج", "الحاجة", "حاج", "حاجة",
    "السيدة", "الآنسة",
]

COMPOUND_PATTERNS = [
    (r'عبد\s{2,}الله', 'عبد الله'),
    (r'عبد\s{2,}الرحمن', 'عبد الرحمن'),
    (r'عبد\s{2,}الرحيم', 'عبد الرحيم'),
    (r'عبد\s{2,}الكريم', 'عبد الكريم'),
    (r'عبد\s{2,}العزيز', 'عبد العزيز'),
    (r'عبد\s{2,}الحميد', 'عبد الحميد'),
    (r'عبد\s{2,}القادر', 'عبد القادر'),
    (r'عبد\s{2,}الغني', 'عبد الغني'),
    (r'عبد\s{2,}المجيد', 'عبد المجيد'),
    (r'عبد\s{2,}الفتاح', 'عبد الفتاح'),
    (r'عبد\s{2,}الستار', 'عبد الستار'),
    (r'عبد\s{2,}المنعم', 'عبد المنعم'),
    (r'عبد\s{2,}الناصر', 'عبد الناصر'),
    (r'عبد\s{2,}الهادي', 'عبد الهادي'),
    (r'عبد\s{2,}الواحد', 'عبد الواحد'),
    (r'عبد\s{2,}الحكيم', 'عبد الحكيم'),
    (r'عبد\s{2,}ال(\w+)', r'عبد ال\1'),
    (r'[أاا]بو\s{2,}(\S)', r'أبو \1'),
    (r'أم\s{2,}(\S)', r'أم \1'),
    (r'محي\s{2,}الدين', 'محي الدين'),
    (r'بهاء\s{2,}الدين', 'بهاء الدين'),
    (r'ضياء\s{2,}الدين', 'ضياء الدين'),
    (r'نور\s{2,}الدين', 'نور الدين'),
    (r'سيف\s{2,}الدين', 'سيف الدين'),
    (r'زين\s{2,}العابدين', 'زين العابدين'),
]

COMPOUND_UNITS = [
    'عبد الله', 'عبد الرحمن', 'عبد الرحيم', 'عبد الكريم',
    'عبد العزيز', 'عبد الحميد', 'عبد القادر', 'عبد الغني',
    'عبد المجيد', 'عبد الفتاح', 'عبد الستار', 'عبد المنعم',
    'عبد الناصر', 'عبد الهادي', 'عبد الواحد', 'عبد الحكيم',
    'أبو فول', 'أبو دقة', 'أبو زيد', 'أبو العمرين',
    'أبو الحسن', 'أبو القاسم', 'أبو بكر', 'أبو طالب',
    'محي الدين', 'بهاء الدين', 'ضياء الدين', 'نور الدين',
    'سيف الدين', 'زين العابدين',
]


def normalize_compounds(name: str) -> str:
    for pattern, replacement in COMPOUND_PATTERNS:
        name = re.sub(pattern, replacement, name)
    return name


def remove_non_arabic(name: str) -> str:
    return re.sub(r"[^\u0600-\u06FF\u0750-\u077F\s]", "", name)


def normalize_spaces(name: str) -> str:
    return re.sub(r'\s{2,}', ' ', name).strip()


def count_name_units(name: str) -> int:
    temp = name
    for i, unit in enumerate(sorted(COMPOUND_UNITS, key=len, reverse=True)):
        temp = temp.replace(unit, f'__U{i}__')
    temp = re.sub(r'عبد\s+\S+', '__UA__', temp)
    # "أبو"/"ابو" (بالهمزة أو بدونها — الإملاء الشائع في الأسماء الفلسطينية
    # كثيراً ما يكتبها بألف عادية بلا همزة) لازم يُعاملا كوحدة واحدة بالتساوي
    temp = re.sub(r'[أا]بو\s+\S+', '__UB__', temp)
    return len(temp.split())


def clean_arabic_name(raw: str):
    if not raw:
        return None
    name = raw
    for title in TITLES_TO_REMOVE:
        name = name.replace(title, "")
    name = normalize_compounds(name)
    name = remove_non_arabic(name)
    name = normalize_spaces(name)
    return name if len(name) >= 4 else None


def estimate_confidence(name, units) -> str:
    if not name:
        return "فشل"
    if units == 4 and all(len(w) >= 2 for w in name.split()):
        return "عالية"
    if units >= 3:
        return "متوسطة"
    return "منخفضة"


# =========================================================
# تحضير الملف (PDF → صورة الصفحة الأولى، مثل ocr_engine.py)
# =========================================================
def prepare_image(file_path: str) -> str:
    p = Path(file_path)
    ext = p.suffix.lower()

    if ext in {".jpg", ".jpeg", ".png", ".webp"}:
        return str(file_path)

    if ext == ".pdf":
        out_prefix = tempfile.mktemp(prefix="ocr_page_")
        result = subprocess.run(
            ["pdftoppm", "-jpeg", "-r", "250", "-f", "1", "-l", "1",
             str(file_path), out_prefix],
            capture_output=True
        )
        candidates = sorted(Path(out_prefix).parent.glob(Path(out_prefix).name + "*.jpg"))
        if candidates:
            return str(candidates[0])
        raise RuntimeError(f"تعذّر تحويل PDF إلى صورة: {result.stderr.decode(errors='ignore')}")

    raise ValueError(f"نوع الملف غير مدعوم: {ext}")


# =========================================================
# محرك الاستخراج — Gemini Flash (سحابي، مجاني ضمن الحدود اليومية)
# ⚠️ يرسل صورة الوثيقة الفعلية إلى Google Gemini API عبر الإنترنت.
# يتطلب متغيّر بيئة GEMINI_API_KEY مضبوطاً على الجهاز (مفتاح مجاني
# من aistudio.google.com بدون بطاقة ائتمان).
# =========================================================
import base64
import os

GEMINI_MODEL = "gemini-3.1-flash-lite"

EXTRACTION_PROMPT = """أنت خبير OCR متخصص في قراءة المستندات الرسمية العربية.

مهمتك: استخرج الاسم الرباعي العربي الكامل من هذه الوثيقة، وحدد نوع الوثيقة.

اتبع هذه الخطوات بالترتيب:

[1] تصحيح الاتجاه — إذا كانت الوثيقة مقلوبة أو مائلة، اقرأها بالاتجاه الصحيح تلقائياً.

[2] تحديد موقع الاسم
- في بطاقات الهوية: ابحث عن حقل "الاسم" / "الاسم الكامل" / "Name"
- في شهادات الميلاد: قد يكون موزّعاً على حقول (اسم المولود/الأب/الجد/العائلة) → ادمجها بمسافة واحدة
- في الاستمارات: ابحث عن "اسم الطالب" / "اسم الطالبة" / "Student Name"

[3] استخراج الاسم — خذ النص العربي فقط، تجاهل الأرقام والرموز والحروف اللاتينية، أزل الألقاب (د./أ./م./دكتور/أستاذ/السيد/الحاج).

[4] تصحيح الأسماء المركّبة (مسافة واحدة فقط بين الجزأين): "عبد الله"، "عبد الرحمن"، "أبو فول"، "محي الدين"، إلخ.

[5] اذكر نوع الوثيقة كما تراه مكتوباً حرفياً على الوثيقة نفسها (العنوان أو الترويسة)، وليس تصنيفاً عاماً.

أعد النتيجة بهذا التنسيق الصارم فقط — سطرين فقط — بدون أي شرح إضافي:
الاسم: [الاسم الرباعي العربي الكامل، أو غير_موجود]
نوع الوثيقة: [كما هو مكتوب على الوثيقة، أو غير محدد]"""


def call_gemini_vision(image_path: str, api_key: str = None) -> str:
    from google import genai
    from google.genai import types

    # المفتاح الشخصي (لو بعته المستخدم من متصفحه) له الأولوية دائماً على
    # مفتاح السيرفر العام في متغيّر البيئة — بهذا يستخدم كل مستخدم حصته
    # الخاصة من Gemini بدل مشاركة حصة واحدة مع الجميع
    api_key = api_key or os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("لا يوجد مفتاح Gemini API — أضف مفتاحك الشخصي من شاشة \"تهيئة مسارات النظام\"، أو اضبط متغيّر البيئة GEMINI_API_KEY على السيرفر")

    ext = Path(image_path).suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            EXTRACTION_PROMPT,
            types.Part.from_bytes(data=img_bytes, mime_type=media_type),
        ],
    )
    return (response.text or "").strip()


def parse_vision_output(raw_output: str):
    """يفصل سطري 'الاسم:' و 'نوع الوثيقة:' من مخرج Claude."""
    raw_name, raw_doc_type = "", ""
    for line in raw_output.splitlines():
        line = line.strip()
        if line.startswith("الاسم:"):
            raw_name = line.split("الاسم:", 1)[1].strip()
        elif line.startswith("نوع الوثيقة:"):
            raw_doc_type = line.split("نوع الوثيقة:", 1)[1].strip()
    if any(x in raw_name for x in ["غير_موجود", "لم يتم", "لا يوجد"]):
        raw_name = ""
    return raw_name, raw_doc_type


# =========================================================
# تحديد نوع الوثيقة — مطابقة اسم الوثيقة الذي حدده Claude ضد doc_types.json
# =========================================================
def _normalize_ar_word(w: str) -> str:
    w = re.sub(r'[\u064B-\u0652\u0670\u0640]', '', w)
    w = re.sub(r'[إأآاٱ]', 'ا', w)
    w = re.sub(r'[ؤئء]', '', w)
    w = w.replace('ة', 'ه').replace('ى', 'ي')
    if w.startswith('ال') and len(w) > 3:
        w = w[2:]
    return w


def _doc_type_words(text: str) -> set:
    words = set()
    for part in re.split(r'[,،]', text):
        for w in re.split(r'\s+', part.strip()):
            w = w.strip()
            if w and not w.isdigit():
                words.add(_normalize_ar_word(w))
    return words


def _overlap_score(a_words: set, b_words: set) -> float:
    if not a_words or not b_words:
        return 0.0
    common = a_words & b_words
    return len(common) / min(len(a_words), len(b_words))


def detect_doc_type(raw_doc_type: str, doc_types: dict) -> str:
    """
    يقارن نص نوع الوثيقة الذي وصفه النموذج (كما هو مكتوب حرفياً على الوثيقة)
    مع كل نوع معرَّف في doc_types.json عبر تطابق بالكلمات — بعد توحيد الألف
    والتاء المربوطة وحذف "الـ" التعريف — بدل الاحتواء النصي الحرفي الهش،
    حتى تُقبل الصياغات المختلفة لنفس الوثيقة (مثل "شهادة ثانوية عامة" مقابل
    "شهادة الدراسة الثانوية العامة لعام 2020"). يفحص أيضاً كل عنصر داخل
    ocr_keywords فعلياً (كانت تُتجاهَل بالكامل سابقاً لأنها قائمة وليست نصاً).
    """
    if not raw_doc_type:
        return "غير محدد"
    if not doc_types:
        return raw_doc_type

    raw_words = _doc_type_words(raw_doc_type)
    if not raw_words:
        return raw_doc_type

    best_score = 0.0
    best_name = None

    for code, info in doc_types.items():
        if not isinstance(info, dict):
            continue

        candidates = []
        for key in ("name_ar", "name_en", "code"):
            v = info.get(key)
            if isinstance(v, str) and v.strip():
                candidates.append(v.strip())

        kws = info.get("ocr_keywords")
        if isinstance(kws, list):
            for kw in kws:
                if isinstance(kw, str) and kw.strip():
                    # عنصر واحد ممكن يحتوي أكثر من عبارة مفصولة بفاصلة (بيانات
                    # قديمة قبل إصلاح شاشة الثوابت) — تُفكّ هنا احتياطاً أيضاً
                    for part in re.split(r'[,،]', kw):
                        part = part.strip()
                        if part:
                            candidates.append(part)

        for cand in candidates:
            score = _overlap_score(raw_words, _doc_type_words(cand))
            if score > best_score:
                best_score = score
                best_name = info.get("name_ar", str(code))

    if best_score >= 0.5:
        return best_name

    return raw_doc_type


# =========================================================
# الدالة الرئيسية
# =========================================================
def extract_document_info(file_path: str, doc_types: dict = None, api_key: str = None) -> dict:
    result = {
        "name": None,
        "parts": 0,
        "confidence": "فشل",
        "doc_type": "غير محدد",
        "status": "❌ فشل",
        "raw_lines": [],
        "error": None,
    }
    try:
        image_path = prepare_image(file_path)
        raw_output = call_gemini_vision(image_path, api_key=api_key)
        result["raw_lines"] = [raw_output]

        raw_name, raw_doc_type = parse_vision_output(raw_output)
        result["doc_type"] = detect_doc_type(raw_doc_type, doc_types or {})

        cleaned = clean_arabic_name(raw_name)

        if cleaned:
            units = count_name_units(cleaned)
            result["name"] = cleaned
            result["parts"] = units
            result["confidence"] = estimate_confidence(cleaned, units)
            result["status"] = "✅ ناجح" if units == 4 else f"⚠️ ناقص ({units} وحدات)"
        else:
            result["error"] = "لم يُعثر على اسم عربي واضح في الوثيقة"

    except Exception as e:
        result["error"] = str(e)

    return result


# =========================================================
# تشغيل مباشر للاختبار المحلي
# =========================================================
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 2:
        print("الاستخدام: python document_extractor.py <مسار_الملف> [doc_types.json]")
        sys.exit(1)

    doc_types_arg = {}
    if len(sys.argv) >= 3:
        with open(sys.argv[2], "r", encoding="utf-8") as f:
            doc_types_arg = json.load(f).get("document_types", {})

    output = extract_document_info(sys.argv[1], doc_types_arg)
    print(json.dumps(output, ensure_ascii=False, indent=2))
