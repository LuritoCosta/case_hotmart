import os

def gerar_tree(diretorio, ignore=['.venv', '__pycache__', '.git']):
    for raiz, dirs, arquivos in os.walk(diretorio):
        # Remove pastas que queremos ignorar para o os.walk não entrar nelas
        dirs[:] = [d for d in dirs if d not in ignore]
        
        nivel = raiz.replace(diretorio, '').count(os.sep)
        indentacao = ' ' * 4 * (nivel)
        print(f'{indentacao}{os.path.basename(raiz)}/')
        sub_indentacao = ' ' * 4 * (nivel + 1)
        for f in arquivos:
            print(f'{sub_indentacao}{f}')

gerar_tree(os.getcwd())