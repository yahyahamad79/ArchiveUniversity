from flask import Blueprint, render_template

# تعريف الـ Blueprint الخاص بالشاشة الرئيسية
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def index():
    # استدعاء ملف الـ HTML المستقل الخاص بلوحة التحكم
    return render_template('dashboard.html')