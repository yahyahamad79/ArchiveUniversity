import pandas as pd

class ExcelRepository:
    def __init__(self, config_manager): self.config_manager = config_manager
    def get_resolved_path(self): return self.config_manager.excel_file
    def load_students_df(self):
        try: return pd.read_excel(self.get_resolved_path(), sheet_name='Students', converters={'student_id': str})
        except: return pd.DataFrame()