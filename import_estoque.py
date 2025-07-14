# import_estoque.py

import openpyxl
import requests
import json
import os

# --- CONFIGURAÇÃO ---
# Caminho COMPLETO para o seu arquivo Excel
# Certifique-se de que o nome do arquivo está correto (ESTOQUE_ABC.xlsx)
EXCEL_FILE_PATH = r'C:\Users\Carlao\OneDrive\oneone\ESTOQUE_ABC.xlsx'

# URL do seu backend no Render (a mesma que você usa no frontend)
# Verifique se esta URL está correta no seu Render Dashboard
BACKEND_URL = 'https://estoque-abc-frontend.onrender.com' # Substitua pela sua URL real do backend

# --- MAPEAMENTO DE CÉLULAS PARA COMPONENTES ---
# Este mapeamento associa o nome do componente no banco de dados com a célula na planilha
# e o tipo de item para o backend processar.
# 'modelo' para CJAs, 'componente' para itens avulsos como assentos, encostos, tampos, porta-livro
STOCK_MAPPING = {
    # ZURICH
    'CJA-06_ASSENTO_ZURICH': {'cell': 'B7', 'db_name': 'ASSENTO-ZURICH', 'type': 'componente'},
    'CJA-05_ASSENTO_ZURICH': {'cell': 'B8', 'db_name': 'ASSENTO-ZURICH', 'type': 'componente'},
    'CJA-04_ASSENTO_ZURICH': {'cell': 'B9', 'db_name': 'ASSENTO-ZURICH', 'type': 'componente'},
    'CJA-03_ASSENTO_ZURICH': {'cell': 'B10', 'db_name': 'ASSENTO-ZURICH', 'type': 'componente'},

    'CJA-06_ENCOSTO_ZURICH': {'cell': 'F7', 'db_name': 'ENCOSTO-ZURICH', 'type': 'componente'},
    'CJA-05_ENCOSTO_ZURICH': {'cell': 'F8', 'db_name': 'ENCOSTO-ZURICH', 'type': 'componente'},
    'CJA-04_ENCOSTO_ZURICH': {'cell': 'F9', 'db_name': 'ENCOSTO-ZURICH', 'type': 'componente'},
    'CJA-03_ENCOSTO_ZURICH': {'cell': 'F10', 'db_name': 'ENCOSTO-ZURICH', 'type': 'componente'},

    # MASTICMOL (usando as células da imagem que você enviou)
    'CJA-06_ASSENTO_MASTICMOL': {'cell': 'B15', 'db_name': 'ASSENTO-MASTICMOL', 'type': 'componente'},
    'CJA-05_ASSENTO_MASTICMOL': {'cell': 'B16', 'db_name': 'ASSENTO-MASTICMOL', 'type': 'componente'},
    'CJA-04_ASSENTO_MASTICMOL': {'cell': 'B17', 'db_name': 'ASSENTO-MASTICMOL', 'type': 'componente'},
    'CJA-03_ASSENTO_MASTICMOL': {'cell': 'B18', 'db_name': 'ASSENTO-MASTICMOL', 'type': 'componente'},

    'CJA-06_ENCOSTO_MASTICMOL': {'cell': 'F15', 'db_name': 'ENCOSTO-MASTICMOL', 'type': 'componente'},
    'CJA-05_ENCOSTO_MASTICMOL': {'cell': 'F16', 'db_name': 'ENCOSTO-MASTICMOL', 'type': 'componente'},
    'CJA-04_ENCOSTO_MASTICMOL': {'cell': 'F17', 'db_name': 'ENCOSTO-MASTICMOL', 'type': 'componente'},
    'CJA-03_ENCOSTO_MASTICMOL': {'cell': 'F18', 'db_name': 'ENCOSTO-MASTICMOL', 'type': 'componente'},

    # TAMPOS
    'CJA-06_TAMPO_MDF': {'cell': 'B24', 'db_name': 'TAMPO-MDF', 'type': 'componente'},
    'CJA-05_TAMPO_MDF': {'cell': 'B25', 'db_name': 'TAMPO-MDF', 'type': 'componente'},
    'CJA-04_TAMPO_MDF': {'cell': 'B26', 'db_name': 'TAMPO-MDF', 'type': 'componente'},
    'CJA-03_TAMPO_MDF': {'cell': 'B27', 'db_name': 'TAMPO-MDF', 'type': 'componente'},

    'CJA-06_TAMPO_PLASTICO': {'cell': 'F24', 'db_name': 'TAMPO-PLASTICO', 'type': 'componente'},
    'CJA-05_TAMPO_PLASTICO': {'cell': 'F25', 'db_name': 'TAMPO-PLASTICO', 'type': 'componente'},
    'CJA-04_TAMPO_PLASTICO': {'cell': 'F26', 'db_name': 'TAMPO-PLASTICO', 'type': 'componente'},
    'CJA-03_TAMPO_PLASTICO': {'cell': 'F27', 'db_name': 'TAMPO-PLASTICO', 'type': 'componente'},

    'CJA-06_TAMPO_MASTICMOL': {'cell': 'I24', 'db_name': 'TAMPO-MASTICMOL', 'type': 'componente'},
    'CJA-05_TAMPO_MASTICMOL': {'cell': 'I25', 'db_name': 'TAMPO-MASTICMOL', 'type': 'componente'},
    'CJA-04_TAMPO_MASTICMOL': {'cell': 'I26', 'db_name': 'TAMPO-MASTICMOL', 'type': 'componente'},
    'CJA-03_TAMPO_MASTICMOL': {'cell': 'I27', 'db_name': 'TAMPO-MASTICMOL', 'type': 'componente'},

    # PORTA-LIVRO (item geral)
    'PORTA_LIVRO_GERAL': {'cell': 'K7', 'db_name': 'PORTA-LIVRO', 'type': 'componente'},
}


def import_stock_from_excel():
    if not os.path.exists(EXCEL_FILE_PATH):
        print(f"ERRO: Arquivo Excel não encontrado no caminho: {EXCEL_FILE_PATH}")
        print("Por favor, verifique se o caminho e o nome do arquivo estão corretos.")
        return

    try:
        workbook = openpyxl.load_workbook(EXCEL_FILE_PATH)
        sheet = workbook.active # Assume que os dados estão na primeira aba ativa

        # Use um dicionário para agregar as quantidades para cada componente único
        aggregated_stock_data = {}

        for key, item_info in STOCK_MAPPING.items():
            cell_ref = item_info['cell']
            db_name = item_info['db_name']

            try:
                quantity = sheet[cell_ref].value
                # Garante que a quantidade é um número e não None
                if quantity is None:
                    quantity = 0
                elif not isinstance(quantity, (int, float)):
                    # Tenta converter para int, caso seja um texto numérico
                    try:
                        quantity = int(quantity)
                    except ValueError:
                        print(f"AVISO: Quantidade inválida '{quantity}' na célula {cell_ref} para {db_name}. Usando 0.")
                        quantity = 0
                
                # Arredonda para inteiro se for float (para quantidades de estoque)
                quantity = int(quantity)

                # Agrega a quantidade para o componente
                aggregated_stock_data[db_name] = aggregated_stock_data.get(db_name, 0) + quantity

            except Exception as e:
                print(f"ERRO ao ler célula {cell_ref} para {db_name}: {e}")
                print(f"Adicionando {db_name} com quantidade 0 devido ao erro.")
                # Se houver um erro de leitura, garanta que o componente seja inicializado com 0 se ainda não estiver
                aggregated_stock_data[db_name] = aggregated_stock_data.get(db_name, 0) + 0 # Adiciona 0 em caso de erro

        # Converte os dados agregados para o formato de lista esperado pelo backend
        stock_data_to_send = []
        for comp_name, total_qty in aggregated_stock_data.items():
            stock_data_to_send.append({
                'componente': comp_name,
                'quantidade': total_qty
            })

        # Envia os dados para o backend
        import_endpoint = f"{BACKEND_URL}/import_initial_stock"
        print(f"\nEnviando dados para o backend: {import_endpoint}")
        print(f"Dados a serem enviados: {json.dumps(stock_data_to_send, indent=2)}")

        response = requests.post(import_endpoint, json=stock_data_to_send)

        if response.status_code == 200:
            print("\nImportação de estoque concluída com sucesso!")
            print(f"Resposta do backend: {response.json()}")
        else:
            print(f"\nERRO na importação de estoque. Status: {response.status_code}")
            print(f"Resposta do backend: {response.text}")

    except FileNotFoundError:
        print(f"ERRO: O arquivo Excel não foi encontrado em '{EXCEL_FILE_PATH}'.")
        print("Por favor, verifique o caminho e o nome do arquivo.")
    except Exception as e:
        print(f"Ocorreu um erro inesperado durante a importação: {e}")

if __name__ == "__main__":
    print("Iniciando importação de estoque do Excel...")
    import_stock_from_excel()
    print("\nProcesso de importação finalizado.")

