"""
id_photo_extractor.py — يقص الصورة الشخصية (وجه وكتفين) من صور بطاقات
الهوية/الصور الشخصية تلقائياً، لاستخدامها ضمن خط "الأتمتة الشاملة".

الخوارزمية تم بناؤها وتصحيحها والتحقق منها فعلياً على بطاقة هوية فلسطينية
حقيقية (وليست نظرية) — راجع التعليقات داخل كل دالة لتفاصيل الأخطاء
الحقيقية التي أدت لكل قرار تصميمي هنا.

الاستخدام:
    from id_photo_extractor import extract_id_photo_bytes
    photo_bytes, info = extract_id_photo_bytes("id_card.jpg")
    if photo_bytes:
        with open("out.jpg", "wb") as f:
            f.write(photo_bytes)
"""

import io

from PIL import Image, ImageOps
import cv2
import numpy as np


def _correct_orientation(image_path: str) -> Image.Image:
    """
    خطوة إلزامية أولى دائماً — صور الموبايل غالباً فيها بيانات دوران EXIF
    (خصوصاً orientation=6) تخلي البيانات الخام "مستلقية" بينما العرض
    البصري بيصححها تلقائياً. تجاهل هذه الخطوة يجعل أي إحداثيات قص تتطابق
    مع الصورة المعروضة بصرياً لكن ليس مع البيانات الخام الفعلية.
    """
    img = Image.open(image_path)
    return ImageOps.exif_transpose(img).convert("RGB")


def _detect_face_in_region(bgr: np.ndarray, region=None):
    """
    يكشف الوجه داخل منطقة محددة من الصورة (أو الصورة كاملة لو region=None)،
    ويرجّع إحداثياته بالنسبة للصورة الكاملة (مش المنطقة الفرعية).
    """
    if region is not None:
        rx, ry, rw, rh = region
        sub = bgr[ry:ry + rh, rx:rx + rw]
    else:
        sub = bgr
        rx, ry = 0, 0
    if sub.size == 0:
        return None
    gray = cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=4, minSize=(40, 40))
    if len(faces) == 0:
        return None
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    fx, fy, fw, fh = faces[0]
    return (fx + rx, fy + ry, fw, fh)


def _detect_blue_background_box(bgr: np.ndarray):
    """
    يكتشف صندوق الصورة الشخصية عبر الخلفية الزرقاء النمطية لبطاقات الهوية.

    ملاحظة مهمة (من تجربة فعلية): الخلفية الزرقاء أحياناً تنقسم لمنطقتين
    منفصلتين بسبب عناصر داكنة فوقها (شعر الرأس تحديداً يقطع استمرارية
    اللون في المنتصف). كيرنل إغلاق مربع صغير غير كافٍ لسدّ الفجوة (ينتج
    قصاً ناقصاً — نصف الوجه فقط). كيرنل إغلاق مستطيل عريض أفقياً (لا مربع)
    يسدّ الفجوة الأفقية الصغيرة بين نصفي الصورة تحديداً، من غير ما يدمج
    عناصر زرقاء بعيدة (كالختم الرسمي أسفل الصورة، الذي تفصله مسافة أكبر
    بكثير من عرض الكيرنل).

    ملاحظة إضافية من تجربة فعلية ثانية: ارتفاع الكيرنل لازم يكون صغيراً
    جداً (لا يتعدى ~5 بكسل) — ارتفاع أكبر (جُرِّب 25) بيسدّ الفجوة
    الرأسية بين الصورة والختم تحته في بعض البطاقات (لو المسافة بينهم
    قريبة)، فيدمجهم في صندوق واحد ويطلع القص طويلاً بزيادة يشمل الختم.
    الفجوة اللي محتاجين نسدّها (شعر الرأس المنقسم) أفقية بالأساس، فمفيش
    داعي لارتفاع كبير من الأصل.
    """
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    lower_blue = np.array([90, 60, 40])
    upper_blue = np.array([140, 255, 255])
    mask = cv2.inRange(hsv, lower_blue, upper_blue)

    close_kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (60, 5))
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, np.ones((10, 10), np.uint8))

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = [c for c in contours if cv2.contourArea(c) > 5000]
    if not contours:
        return None

    contours.sort(key=cv2.contourArea, reverse=True)
    return cv2.boundingRect(contours[0])


def _verify_crop_quality(crop_rgb: np.ndarray) -> dict:
    """
    تحقق إحصائي بديل عن الاعتماد على المعاينة البصرية وحدها.

    ملاحظة من تجربة فعلية: نقطة فحص واحدة ثابتة (منتصف القص) غير كافية —
    في حالة شخص يرتدي حجاباً مثلاً، منطقة "المنتصف" الثابتة ممكن تقع
    جزئياً على قماش الحجاب لا البشرة، فيضعف إشارة الفحص رغم أن القص صحيح
    فعلياً. الحل: أخذ عدة نقاط صغيرة موزّعة داخل منطقة الوجه المتوقّعة
    (لا الحواف، ولا أسفل القص حيث الكتفين/الملابس) وأخذ أفضل نقطة بينها
    كممثل — لو نقطة واحدة على الأقل بشرة واضحة، القص صحيح، بغض النظر عن
    شكل الشعر/الحجاب/النظارة. هذا أدق من متوسط كل المنطقة لأن المتوسط قد
    يُخفي بقعة بشرة واضحة وسط بقع تانية غير بشرة.
    """
    h, w, _ = crop_rgb.shape
    # شبكة نقاط داخل الثلث العلوي والأوسط تحديداً (منطقة الوجه المتوقعة
    # في أي صورة شخصية نمطية)، بعيداً عن حواف القص يميناً/يساراً حيث
    # الخلفية أو حواف البطاقة، وبعيداً عن أسفل القص حيث الكتفين/الملابس
    y_fracs = [0.28, 0.36, 0.44, 0.52]
    x_fracs = [0.38, 0.46, 0.54, 0.62]
    patch_h, patch_w = max(1, int(h * 0.06)), max(1, int(w * 0.06))

    best_score = -999.0
    best_rgb = None
    for yf in y_fracs:
        for xf in x_fracs:
            cy, cx = int(h * yf), int(w * xf)
            patch = crop_rgb[cy:cy + patch_h, cx:cx + patch_w, :]
            if patch.size == 0:
                continue
            mean_rgb = patch.reshape(-1, 3).mean(axis=0)
            # درجة "شبه بالبشرة": الأحمر أعلى وضوحاً من الأخضر والأزرق معاً
            score = float(mean_rgb[0] - max(mean_rgb[1], mean_rgb[2]))
            if score > best_score:
                best_score = score
                best_rgb = mean_rgb

    looks_like_skin = bool(best_score > 8)  # هامش أمان بسيط بدل صفر تماماً
    return {
        "best_patch_rgb": best_rgb.round(1).tolist() if best_rgb is not None else None,
        "skin_score": round(best_score, 1),
        "looks_like_skin": looks_like_skin,
    }


def extract_id_photo_bytes(image_path: str, height_ratio: float = 1.3, top_fraction: float = 0.22,
                            inset_x: float = 0.10, inset_top: float = 0.05, inset_bottom: float = 0.10):
    """
    يرجّع (photo_bytes, info) — photo_bytes هي بايتات JPEG جاهزة للحفظ أو
    الإرسال، أو None لو تعذّر تحديد الصورة الشخصية. info فيها تفاصيل
    تشخيصية (الطريقة المستخدَمة، وهل القص يبدو صحيحاً إحصائياً أم لا).

    ملاحظة من تجربة فعلية خامسة: الناتج الآن بمقاس ثابت **4×6** (نسبة
    عرض:ارتفاع = 4:6) بدل نسبة متغيّرة حسب أبعاد الوجه — وده بتركيز أكبر
    على الوجه (الوجه بيملأ نسبة أكبر من الإطار). الارتفاع الكلي = ارتفاع
    الوجه المكتشَف × height_ratio، والعرض = الارتفاع × (4/6) دائماً (مش
    مرتبط بعرض الوجه نفسه، فيضمن نسبة العرض:الارتفاع الصحيحة تماماً في كل
    مرة). القيم الافتراضية هنا (1.3 وtop_fraction=0.22) تم اختبارها فعلياً
    على 4 بطاقات حقيقية مختلفة والتحقق من عدم قص الوجه في أي منها — قيمة
    أكثر عدوانية (1.2) جُرِّبت لكنها سبّبت عدم استقرار في إعادة اكتشاف
    الوجه على القص الناتج في إحدى الحالات، فتم التراجع عنها.
    """
    try:
        pil_img = _correct_orientation(image_path)
        rgb = np.array(pil_img)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # لا نفترض أي موقع ثابت للصورة على الوثيقة (يمين/شمال) — نبحث عن
        # الوجه في كل الصورة دائماً، وأيضاً داخل صندوق الخلفية الزرقاء (لو
        # وُجد) لتضييق البحث، ثم نختار الأكبر من بين كل المرشحين المكتشَفين.
        # ملاحظة من تجربة فعلية سادسة: تصميمات بطاقات مختلفة (بطاقة شخصية
        # مؤقتة مثلاً) ممكن يكتشف فيها صندوق أزرق غلط تماماً (الختم الرسمي
        # تحت الصورة له حبر أزرق كمان)، فيقيّد البحث عن الوجه بمنطقة غلط
        # ويكتشف شكلاً صغيراً مضلِّلاً بدل الوجه الحقيقي الأكبر. الاعتماد
        # على "الأكبر حجماً بين كل المرشحين" (بدل "أول ما يُكتشف") يتجاوز
        # هذه المشكلة تلقائياً، لأن الوجه الحقيقي يكون عادة أكبر بكثير من
        # أي اكتشاف زائف.
        blue_box = _detect_blue_background_box(bgr)
        candidates = []
        face_in_blue = _detect_face_in_region(bgr, region=blue_box)
        if face_in_blue is not None:
            candidates.append(face_in_blue)
        face_in_full = _detect_face_in_region(bgr, region=None)
        if face_in_full is not None:
            candidates.append(face_in_full)
        face_box = max(candidates, key=lambda f: f[2] * f[3]) if candidates else None

        if face_box is not None:
            fx, fy, fw, fh = face_box
            total_h = fh * height_ratio
            total_w = total_h * (4 / 6)
            top = fy - fh * top_fraction
            bottom = top + total_h
            cx = fx + fw / 2
            left = cx - total_w / 2
            right = cx + total_w / 2
            left, top, right, bottom = int(left), int(top), int(right), int(bottom)
            left = max(0, left)
            top = max(0, top)
            right = min(pil_img.width, right)
            bottom = min(pil_img.height, bottom)
            method = "كشف الوجه (4×6)"
        elif blue_box is not None:
            # احتياطي أخير: مفيش وجه واضح لكن فيه خلفية زرقاء — نرجع لمنطق
            # التقليم الداخلي القديم بدل ما نفشل تماماً (أقل دقة، لكن أفضل من لا شيء)
            x, y, w, h = blue_box
            left = x + int(w * inset_x)
            right = x + w - int(w * inset_x)
            top = y + int(h * inset_top)
            bottom = y + h - int(h * inset_bottom)
            method = "خلفية زرقاء (بدون كشف وجه واضح)"
        else:
            return None, {"error": "تعذّر تحديد موقع الصورة الشخصية"}

        crop = pil_img.crop((left, top, right, bottom))

        quality = _verify_crop_quality(np.array(crop))

        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=92)
        return buf.getvalue(), {"method": method, "size": crop.size, **quality}
    except Exception as e:
        return None, {"error": str(e)}
