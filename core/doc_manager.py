import os
import json

class DocTypeManager:
    def __init__(self, base_dir):
        self.doc_types_file = os.path.join(base_dir, "config", "doc_types.json")
        self.data = self._load()

    def _load(self):
        if os.path.exists(self.doc_types_file):
            with open(self.doc_types_file, 'r', encoding='utf-8') as f: return json.load(f)
        return {"document_types": {}}

    def save_types(self, data):
        with open(self.doc_types_file, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)
        self.data = data

    def get_types_info(self): return self.data.get('document_types', {})
    def get_ordered_columns(self): return [col for col, info in sorted(self.get_types_info().items(), key=lambda x: x[1].get('order', 999))]
    def is_required(self, col_name): return self.get_types_info()[col_name].get('required', True) if col_name in self.get_types_info() else True