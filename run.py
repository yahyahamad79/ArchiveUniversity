import os
import webbrowser
from threading import Timer
from flask import Flask

# استيراد المكونات الخلفية
from core.config_manager import ConfigManager
from core.doc_manager import DocTypeManager
from core.excel_repo import ExcelRepository
from core.archive_service import ArchiveService

# استيراد الشاشات المنفصلة (Blueprints)
from modules.dashboard.routes import dashboard_bp
from modules.archive.routes import archive_bp

def create_app():
    app = Flask(__name__, template_folder='templates')
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

    # تهيئة الخدمات وحفظها داخل كائن التطبيق app لتكون متاحة لكل الشاشات
    app.config_manager = ConfigManager(BASE_DIR)
    app.doc_manager = DocTypeManager(BASE_DIR)
    app.excel_repo = ExcelRepository(app.config_manager)
    app.archive_service = ArchiveService(app.config_manager, app.doc_manager, app.excel_repo)

    # 🔗 ربط الشاشات المنفصلة مع التطبيق الرئيسي
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(archive_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    # فتح المتصفح تلقائياً بعد ثانيتين
    Timer(2, lambda: webbrowser.open_new('http://127.0.0.1:5000')).start()
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)