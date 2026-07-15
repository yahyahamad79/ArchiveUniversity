import pandas as pd
from modules.excel_manager import find_student_by_filename

df = pd.DataFrame([
    {'ID': '12345', 'الاسم': 'عبدالله محمد'},
    {'ID': '54321', 'الاسم': 'أحمد علي'}
])

print('numeric', find_student_by_filename(df, '12345_BC.jpg'))
print('name', find_student_by_filename(df, 'عبدالله_محمد.jpg'))
print('fuzzy', find_student_by_filename(df, 'احمد-علي.jpg'))
