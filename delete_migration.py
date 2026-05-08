import os

file_path = r'C:\Users\hoshi\pi-fiscalia\feeds\migrations\0005_alter_tag_ordering.py'
if os.path.exists(file_path):
    os.remove(file_path)
    print(f"✓ Arquivo {file_path} deletado com sucesso")
else:
    print(f"✗ Arquivo não encontrado: {file_path}")
