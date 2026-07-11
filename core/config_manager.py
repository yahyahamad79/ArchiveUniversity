import os
import json

class ConfigManager:
    def __init__(self, base_dir):
        self.config_file = os.path.join(base_dir, "config", "archive_config.json")
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r', encoding='utf-8') as f: return json.load(f)
        return {'archive_path': '', 'excel_file': ''}

    def save_config(self, archive_path, excel_file):
        self.config['archive_path'] = archive_path
        self.config['excel_file'] = excel_file
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w', encoding='utf-8') as f: json.dump(self.config, f, ensure_ascii=False, indent=2)

    @property
    def archive_path(self): return self.config.get('archive_path', '')
    @property
    def excel_file(self): return self.config.get('excel_file', '')