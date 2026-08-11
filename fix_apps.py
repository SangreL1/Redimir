import os
import glob

for filepath in glob.glob('apps/*/apps.py'):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    app_name = os.path.basename(os.path.dirname(filepath))
    content = content.replace(f"name = '{app_name}'", f"name = 'apps.{app_name}'")
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
print('Fixed apps.py files')
