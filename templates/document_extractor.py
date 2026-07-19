"""
document_extractor.py — استخراج الاسم العربي ونوع الوثيقة عبر Claude Vision (سحابي)
=====================================================================================
⚠️ يرسل صورة الوثيقة فعلياً إلى Anthropic API عبر الإنترنت (تم اعتماد هذا
المسار بدل PaddleOCR المحلي بسبب موارد جهاز محدودة). يتطلب:
  - متغيّر بيئة ANTHROPIC_API_KEY مضبوطاً على الجهاز
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
    temp = re.sub(r'أبو\s+\S+', '__UB__', temp)
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
# محرك الاستخراج — Claude Vision (سحابي)
# ⚠️ يرسل صورة الوثيقة الفعلية إلى Anthropic API عبر الإنترنت.
# يتطلب متغيّر بيئة ANTHROPIC_API_KEY مضبوطاً على الجهاز.
# =========================================================
import base64

MODEL = "claude-opus-4-5"
MAX_TOKENS = 250

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


def call_claude_vision(image_path: str) -> str:
    import anthropic

    ext = Path(image_path).suffix.lower()
    media_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    media_type = media_map.get(ext, "image/jpeg")

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    client = anthropic.Anthropic()  # يقرأ المفتاح تلقائياً من ANTHROPIC_API_KEY
    response = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                {"type": "text", "text": EXTRACTION_PROMPT},
            ],
        }],
    )
    return response.content[0].text.strip()


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
def detect_doc_type(raw_doc_type: str, doc_types: dict) -> str:
    """
    يعمل مع أي بنية تقريباً لِـ doc_types (dict) — يقارن ما ذكره النموذج
    مع القيم النصية الموجودة في doc_types.json، وإن لم يجد تطابقاً يعيد
    ما ذكره النموذج نفسه كما هو (أفضل من "غير محدد" لأنه معلومة حقيقية من الوثيقة).
    """
    if not raw_doc_type:
        return "غير محدد"
    if not doc_types:
        return raw_doc_type

    for code, info in doc_types.items():
        candidates = []
        if isinstance(info, dict):
            for v in info.values():
                if isinstance(v, str) and v.strip():
                    candidates.append(v.strip())
        elif isinstance(info, str):
            candidates.append(info.strip())
        candidates.append(str(code))

        for cand in candidates:
            if len(cand) >= 3 and (cand in raw_doc_type or raw_doc_type in cand):
                return info.get("name_ar", cand) if isinstance(info, dict) else cand

    return raw_doc_type


# =========================================================
# الدالة الرئيسية
# =========================================================
def extract_document_info(file_path: str, doc_types: dict = None) -> dict:
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
        raw_output = call_claude_vision(image_path)
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
