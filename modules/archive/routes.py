from flask import Blueprint, render_template, current_app, jsonify, request

# تعريف الـ Blueprint الخاص بشاشة الأرشيف الفرعية
archive_bp = Blueprint('archive', __name__)

@archive_bp.route('/archive')
def index():
    # الوصول إلى الخدمات المشتركة الممررة للتطبيق
    config_manager = current_app.config_manager
    doc_manager = current_app.doc_manager
    return render_template(
        'archive.html',
        archive_path=config_manager.archive_path,
        excel_file=config_manager.excel_file,
        doc_types_path=doc_manager.doc_types_file
    )

# روابط الـ API الخاصة بالأرشيف فقط
@archive_bp.route('/api/stats')
def stats():
    df = current_app.excel_repo.load_students_df()
    return jsonify({'student_count': len(df) if not df.empty else 0})

@archive_bp.route('/api/search')
def search():
    df = current_app.excel_repo.load_students_df()
    students = []
    if not df.empty:
        for _, row in df.head(5).iterrows():
            sid = str(row['student_id'])
            students.append({
                'student_id': sid, 
                'full_name': row.get('full_name', 'طالب'), 
                'documents': current_app.archive_service.get_student_documents(sid), 
                'summary': current_app.archive_service.get_delivery_summary(sid)
            })
    return jsonify(students)