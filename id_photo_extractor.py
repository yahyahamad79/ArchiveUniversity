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


def _detect_face_box(bgr: np.ndarray):
    """احتياطي (fallback) عند غياب خلفية زرقاء واضحة — كشف الوجه مباشرة."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    face_cascade = cv2.CascadeClassifier(cascade_path)
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
    if len(faces) == 0:
        return None
    faces = sorted(faces, key=lambda f: f[2] * f[3], reverse=True)
    x, y, w, h = faces[0]
    margin_x, margin_top, margin_bottom = int(w * 0.6), int(h * 0.7), int(h * 1.3)
    return (
        max(0, x - margin_x),
        max(0, y - margin_top),
        w + 2 * margin_x,
        h + margin_top + margin_bottom,
    )


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


def extract_id_photo_bytes(image_path: str, inset_x: float = 0.10, inset_top: float = 0.05, inset_bottom: float = 0.10):
    """
    يرجّع (photo_bytes, info) — photo_bytes هي بايتات JPEG جاهزة للحفظ أو
    الإرسال، أو None لو تعذّر تحديد الصورة الشخصية. info فيها تفاصيل
    تشخيصية (الطريقة المستخدَمة، وهل القص يبدو صحيحاً إحصائياً أم لا).

    ملاحظة من تجربة فعلية ثالثة: صندوق الخلفية الزرقاء المكتشَف بيحتوي
    عادة على هامش زائد حوالين الوجه (خلفية زرقاء فاضية فوق الرأس وعلى
    الجانبين) — القص الأدق مش بإضافة هامش خارجي حوله (padding) زي
    الإصدارات الأولى، لكن بتقليم هامش داخلي (inset) نسبة من أبعاد الصندوق
    نفسه، أفقياً ورأسياً. النسب الافتراضية هنا تم التحقق منها عملياً عبر
    كشف الوجه (Haar Cascade) على القص الناتج والتأكد من بقاء هامش أمان
    حقيقي حول الوجه المكتشَف على أكثر من بطاقة هوية حقيقية — قيمة أولى
    أكثر عدوانية لـ inset_bottom (0.18) تم تجربتها لكنها كادت تقصّ ذقن
    الوجه في إحدى الحالات الحقيقية (هامش 0 بكسل بالظبط)، فتم تخفيضها.
    """
    try:
        pil_img = _correct_orientation(image_path)
        rgb = np.array(pil_img)
        bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        box = _detect_blue_background_box(bgr)
        method = "خلفية زرقاء"
        if box is None:
            box = _detect_face_box(bgr)
            method = "كشف الوجه (احتياطي)"
        if box is None:
            return None, {"error": "تعذّر تحديد موقع الصورة الشخصية"}

        x, y, w, h = box
        left = x + int(w * inset_x)
        right = x + w - int(w * inset_x)
        top = y + int(h * inset_top)
        bottom = y + h - int(h * inset_bottom)
        crop = pil_img.crop((left, top, right, bottom))

        quality = _verify_crop_quality(np.array(crop))

        buf = io.BytesIO()
        crop.save(buf, format="JPEG", quality=92)
        return buf.getvalue(), {"method": method, "size": crop.size, **quality}
    except Exception as e:
        return None, {"error": str(e)}
