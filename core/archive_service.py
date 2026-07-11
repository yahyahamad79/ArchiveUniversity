import os

class ArchiveService:
    def __init__(self, config_manager, doc_manager, excel_repo):
        self.config = config_manager; self.doc_manager = doc_manager; self.repo = excel_repo
    def resolve_student_folder(self, sid): return os.path.join(self.config.archive_path, str(sid))
    def get_student_documents(self, student_id):
        folder = self.resolve_student_folder(student_id)
        files = [{'filename': f} for f in os.listdir(folder)] if os.path.exists(folder) else []
        docs = []
        for col in self.doc_manager.get_ordered_columns():
            matched = [f for f in files if col in f['filename']]
            docs.append({'doc_name': col, 'is_required': self.doc_manager.is_required(col), 'status_display': '✅ جاهز' if matched else '❌ ناقص', 'card_class': 'delivered' if matched else 'missing', 'files': matched})
        return docs
    def get_delivery_summary(self, student_id):
        docs = self.get_student_documents(student_id)
        req = [d for d in docs if d['is_required']]
        missing = [d for d in req if 'ناقص' in d['status_display']]
        return {'total_required': len(req), 'delivered': len(req)-len(missing), 'is_complete': len(missing)==0}