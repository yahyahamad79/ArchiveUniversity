import os
import json
import shutil
import traceback
import webbrowser
from io import BytesIO
from datetime import datetime
from threading import Timer              # 👈 استيراد التايمر لمنع انهيار السيرفر
import pandas as pd
from flask import Flask, render_template_string, request, send_file, jsonify

# استيراد ممرات الـ Blueprints لشاشة الأرشيف وشاشة ثوابت النظام الجديدة
from modules.archive_update import init_archive_routes
from modules.system_constants import init_constants_routes

# =====================================================================
# قالب الـ HTML للشاشة الرئيسية للتحكم (Dashboard)
# =====================================================================
MAIN_DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>لوحة التحكم الرئيسية - نظام الأرشيف</title>
    <style>
        :root { --navy:#123b5d; --blue:#1d6fa5; --mint:#1f9d79; --ink:#152536; --muted:#66788a; --line:#dce6ee; --surface:#fff; --soft:#f4f8fb; --shadow:0 14px 34px rgba(22, 55, 80, .10); }
        * { margin:0; padding:0; box-sizing:border-box; }
        body { min-height:100vh; font-family:'Segoe UI', Tahoma, sans-serif; color:var(--ink); background:#f4f7fa; line-height:1.55; padding: 20px; }
        .container { max-width:1000px; margin: 40px auto; }
        .main-header { padding:32px; border-radius:20px; background:linear-gradient(135deg,#123b5d,#1d6fa5); color:#fff; text-align:center; box-shadow:var(--shadow); margin-bottom: 30px; }
        .main-header h1 { font-size:2rem; margin-bottom: 8px; letter-spacing:-0.5px; }
        .main-header p { font-size:0.95rem; opacity:0.9; }
        
        /* أقسام واجهة التحكم */
        .dashboard-section { background: var(--surface); border: 1px solid var(--line); border-radius: 18px; padding: 28px; margin-bottom: 28px; box-shadow: var(--shadow); }
        .section-title { font-size: 1.35rem; font-weight:700; color: var(--navy); border-bottom: 2px solid #edf2f6; padding-bottom: 12px; margin-bottom: 20px; display: flex; align-items: center; gap: 10px; }
        
        /* بطاقات القائمة المنسقة */
        .grid-menu { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; }
        .menu-card { background: #f8fbfd; border: 1px solid #cbd9e4; border-radius: 14px; padding: 22px; text-decoration: none; color: var(--ink); display: flex; flex-direction: column; gap: 10px; transition: 0.2s cubic-bezier(0.4, 0, 0.2, 1); }
        .menu-card:hover { transform: translateY(-4px); border-color: var(--blue); background: #fff; box-shadow: 0 10px 24px rgba(29,111,165,0.12); }
        .menu-card h3 { color: var(--blue); font-size: 1.2rem; display: flex; align-items: center; gap: 8px; }
        .menu-card p { font-size: 0.88rem; color: var(--muted); line-height: 1.5; }
        
        /* تنسيق مخصص لقسم ثوابت النظام */
        .section-constants { border-top: 4px solid #6652a6; }
        .btn-constant-card { background: #faf9ff; border-color: #d6cfea; }
        .btn-constant-card:hover { border-color: #6652a6; box-shadow: 0 10px 24px rgba(102,82,166,0.12); }
        .btn-constant-card h3 { color: #6652a6; }
    </style>
</head>
<body>

<div class="container">
    <div class="main-header">
        <h1>🎓 نظام إدارة أرشيف الطلاب</h1>
        <p>البوابة الإدارية الموحدة للتحكم بالأرشيف المادي والرقمي وثوابت النظام</p>
    </div>

    <div class="dashboard-section">
        <div class="section-title">📁 إدارة الملفات والأرشيف الأكاديمي</div>
        <div class="grid-menu">
            <a href="/archive" class="menu-card">
                <h3>📁 أرشيف ملفات الطلاب</h3>
                <p>البحث عن وثائق الطلاب، استعراض المجلدات والمستندات المادية، إجراء التحديث الشامل، والمزامنة التلقائية لبيانات الحالات.</p>
            </a>
        </div>
    </div>

    <div class="dashboard-section section-constants">
        <div class="section-title" style="color: #6652a6;">⚙️ ثوابت النظام الإدارية</div>
        <div class="grid-menu">
            <a href="/Doc_Type" class="menu-card btn-constant-card">
                <h3>📝 إعداد أنواع الوثائق (Doc_Type)</h3>
                <p>إدارة وتخصيص وثائق الطلاب: إضافة أو حذف وثيقة، تعيين الأسماء باللغتين، تحديد الرموز الخاصة بالملفات (Code)، وضبط إلزامية الوثائق وترتيبها.</p>
            </a>
        </div>
    </div>
</div>

</body>
</html>
"""

# =====================================================================
# الكلاس الأساسي لتشغيل سيرفر النظام وتنسيق الممرات
# =====================================================================
class StudentArchiveApp:
    def __init__(self):
        self.app = Flask(__name__)
        self.base_dir = os.path.dirname(os.path.abspath(__file__))
        
        # تهيئة مسارات الـ Blueprints المحدثة والمستقلة
        self.archive_bp = init_archive_routes(self.base_dir)
        self.constants_bp = init_constants_routes(self.base_dir)
        
        # تسجيل الـ Blueprints داخل تطبيق فلاسك
        self.app.register_blueprint(self.archive_bp)
        self.app.register_blueprint(self.constants_bp)
        
        self.setup_main_routes()

    def setup_main_routes(self):
        # الممر الرئيسي الذي يعرض لوحة التحكم
        @self.app.route('/')
        def index():
            return render_template_string(MAIN_DASHBOARD_TEMPLATE)

    def run(self):
        # تشغيل التايمر لفتح المتصفح تلقائياً عند بدء تشغيل السيرفر بدون مشاكل
        Timer(2, lambda: webbrowser.open_new('http://127.0.0.1:5000')).start()
        self.app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)

# =====================================================================
# التشغيل الرئيسي (Execution Block)
# =====================================================================
if __name__ == '__main__':
    # إنشاء الكائن وتشغيل النظام بالكامل
    archive_system = StudentArchiveApp()
    archive_system.run()