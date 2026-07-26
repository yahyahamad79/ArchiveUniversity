/*
  excel-utils.js — منطق مشترك للتعامل مع ملفات الإكسل، مستخدَم من أكثر من
  شاشة (المطابقة، إدارة الثوابت، المسارات، متابعة اكتمال الوثائق) بدل
  تكرار نفس الدوال بالحرف في كل ملف على حدة. أي إصلاح مستقبلي لهذا المنطق
  يكفي أن يتم هنا مرة واحدة بدل أربع مرات.

  يفترض وجود مكتبة XLSX (SheetJS) محمّلة مسبقاً في الصفحة قبل استخدام
  أي دالة هنا.
*/

// يكتشف صف العناوين الحقيقي بدل افتراض أن الصف الأول دائماً هو العناوين —
// بعض الملفات تبدأ بصف عنوان/شعار مدمج (خلية واحدة فقط تحمل نصاً مثل
// "لوحة معلومات الطلبة") قبل صف العناوين الفعلي، ما يجعل SheetJS يولّد
// مفاتيح وهمية (__EMPTY, __EMPTY_1...) لبقية الأعمدة. الحل: فحص أول 15 صفاً
// خاماً واختيار الصف الذي يحوي أكبر عدد من الخلايا غير الفارغة كصف عناوين.
function detectHeaderRowIndex(ws) {
  const raw = XLSX.utils.sheet_to_json(ws, { header: 1, defval: '', raw: false, blankrows: false });
  let bestIdx = 0, bestCount = -1;
  for (let i = 0; i < Math.min(raw.length, 15); i++) {
    const nonEmpty = (raw[i] || []).filter(c => String(c).trim() !== '').length;
    if (nonEmpty > bestCount) { bestCount = nonEmpty; bestIdx = i; }
  }
  return bestIdx;
}

// لو تم تجاوز صف/صفوف بانر (مثل عنوان مدمج) قبل صف العناوين الحقيقي، يجب
// الحفاظ عليها كما هي بالملف المحفوظ — بدل فقدانها لأن json_to_sheet يبني
// دائماً من الصف 1. يدمج صفوف البانر الأصلية + بيانات الجدول الجديدة بإزاحة.
function mergeWithOriginalBannerRows(originalWs, dataSheet, headerRowIdx) {
  if (!headerRowIdx) return dataSheet; // لا يوجد بانر، لا حاجة لأي دمج
  const merged = {};
  const origRange = originalWs['!ref'] ? XLSX.utils.decode_range(originalWs['!ref']) : null;
  if (origRange) {
    for (let R = origRange.s.r; R < headerRowIdx; R++) {
      for (let C = origRange.s.c; C <= origRange.e.c; C++) {
        const addr = XLSX.utils.encode_cell({ r: R, c: C });
        if (originalWs[addr]) merged[addr] = originalWs[addr];
      }
    }
  }
  const dataRange = dataSheet['!ref'] ? XLSX.utils.decode_range(dataSheet['!ref']) : null;
  let maxR = headerRowIdx - 1;
  let maxC = origRange ? origRange.e.c : 0;
  if (dataRange) {
    for (let R = dataRange.s.r; R <= dataRange.e.r; R++) {
      for (let C = dataRange.s.c; C <= dataRange.e.c; C++) {
        const srcAddr = XLSX.utils.encode_cell({ r: R, c: C });
        if (dataSheet[srcAddr]) {
          const dstAddr = XLSX.utils.encode_cell({ r: R + headerRowIdx, c: C });
          merged[dstAddr] = dataSheet[srcAddr];
        }
      }
    }
    maxR = Math.max(maxR, dataRange.e.r + headerRowIdx);
    maxC = Math.max(maxC, dataRange.e.c);
  }
  merged['!ref'] = XLSX.utils.encode_range({ s: { r: 0, c: 0 }, e: { r: maxR, c: maxC } });
  if (originalWs['!merges']) merged['!merges'] = originalWs['!merges'];
  return merged;
}

// يفرض النوع النصي الحقيقي (t='s') وتنسيق نص ('@') على أعمدة بعينها داخل
// ورقة إكسل مبنية حديثاً — يمنع Excel نفسه من إعادة تفسيرها كأرقام لاحقاً
// (وبالتالي فقدان الأصفار البادئة) حتى لو بدت القيمة رقماً بحتاً.
// colNames: أسماء الأعمدة المطلوب حمايتها (مثل عمود رقم الطالب).
// cols: كل أسماء الأعمدة بترتيبها الحالي في الورقة (لتحديد موقع كل عمود).
function forceTextColumnsInSheet(sheet, colNames, cols, rows) {
  const idxByName = {};
  cols.forEach((c, i) => { idxByName[c] = i; });
  for (const colName of colNames) {
    const colIdx = idxByName[colName];
    if (colIdx === undefined) continue;
    const colLetter = XLSX.utils.encode_col(colIdx);
    for (let r = 0; r < rows.length; r++) {
      const addr = colLetter + (r + 2); // +2: صف العناوين رقم 1
      const cell = sheet[addr];
      if (cell) {
        cell.v = String(cell.v);
        cell.t = 's';
        cell.z = '@';
      }
    }
  }
}
