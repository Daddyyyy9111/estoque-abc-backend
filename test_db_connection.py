import os
import psycopg2
from psycopg2 import Error

# Força o Python a usar UTF-8 para operações de E/S
# Isso pode ajudar a resolver problemas de codificação relacionados ao ambiente
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LC_ALL'] = 'en_US.UTF-8'
os.environ['LANG'] = 'en_US.UTF-8'

# Configurações do seu banco de dados PostgreSQL
DB_HOST = "localhost"
DB_NAME = "estoque_abc" # O nome do banco de dados que você criou no pgAdmin
DB_USER = "postgres"   # O usuário padrão do PostgreSQL
DB_PASSWORD = "12345678" # <<<<< Verifique se esta senha está EXATAMENTE igual à que você definiu no pgAdmin

def test_connection():
    connection = None
    try:
        # Conectar ao banco de dados PostgreSQL
        # client_encoding='UTF8' é adicionado para ajudar com problemas de caracteres especiais
        # sslmode='disable' é adicionado para evitar problemas de SSL em conexões locais de teste
        connection = psycopg2.connect(
            user=DB_USER,
            password=f"{DB_PASSWORD}", # Usando f-string para garantir a representação da string
            host=DB_HOST,
            port="5432", # Porta padrão do PostgreSQL
            database=DB_NAME,
            client_encoding='UTF8',
            sslmode='disable' # Desabilita SSL para conexão local
        )

        # Criar um cursor para executar operações no banco de dados
        cursor = connection.cursor()

        # Exemplo: Executar uma consulta simples para verificar a conexão
        print("Conectado ao PostgreSQL com sucesso!")
        cursor.execute("SELECT version();")
        record = cursor.fetchone()
        print("Você está conectado a - ", record, "\n")

    except (Exception, Error) as error:
        print("Erro ao conectar ao PostgreSQL:")
        print(f"Tipo de erro: {type(error)}")
        print(f"Mensagem de erro: {error}")
        # Tenta imprimir mais detalhes do erro, se disponíveis
        if hasattr(error, 'args') and len(error.args) > 0:
            print(f"Argumentos do erro: {error.args}")
        if hasattr(error, 'diag'): # Para erros mais detalhados do Psycopg2
            print(f"Detalhes de diagnóstico (diag): {error.diag}")
        if hasattr(error, 'pgcode'):
            print(f"Código PG: {error.pgcode}")
        if hasattr(error, 'pgerror'):
            print(f"Mensagem PG: {error.pgerror}")

    finally:
        if connection:
            cursor.close()
            connection.close()
            print("Conexão com o PostgreSQL fechada.")

if __name__ == "__main__":
    test_connection()
