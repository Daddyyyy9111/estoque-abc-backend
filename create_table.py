import psycopg2
import os

# Credenciais do seu banco de dados no Render.com
# Use as credenciais EXATAS do seu estoque-abc-db-v2 do Render
DB_HOST = 'dpg-d1mk6bur433s73dj1jg-a.ohio-postgres.render.com'
DB_NAME = 'estoque_abc_db_v2'
DB_USER = 'sudeste'
DB_PASSWORD = 'WyhYHkW6VGcspUeU4Yv9h3P08MkKEP' # COPIE A SENHA EXATA DO RENDER AQUI
DB_PORT = '5432'

conn = None
cur = None

try:
    print("Tentando conectar ao banco de dados...")
    conn = psycopg2.connect(
        host=DB_HOST,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
        port=DB_PORT,
        sslmode='require' # Garante que a conexão SSL seja usada
    )
    cur = conn.cursor()
    print("Conexão bem-sucedida!")

    # Comando SQL para criar a tabela
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS estoque_atual (
        id SERIAL PRIMARY KEY,
        modelo VARCHAR(255) NOT NULL,
        quantidade INTEGER NOT NULL,
        tampo VARCHAR(255) NOT NULL
    );
    """
    cur.execute(create_table_sql)
    conn.commit() # Salva as alterações no banco de dados
    print("Tabela 'estoque_atual' criada com sucesso ou já existente.")

    # Comando SQL para inserir dados de teste (opcional, para garantir que algo apareça)
    # ON CONFLICT (id) DO NOTHING evita erro se você rodar o script várias vezes
    insert_data_sql = """
    INSERT INTO estoque_atual (modelo, quantidade, tampo) VALUES ('CJA-06B', -11, 'PLASTICO') ON CONFLICT (id) DO NOTHING;
    INSERT INTO estoque_atual (modelo, quantidade, tampo) VALUES ('CJA-04B', 50, 'MDF') ON CONFLICT (id) DO NOTHING;
    """
    cur.execute(insert_data_sql)
    conn.commit() # Salva as alterações
    print("Dados de teste inseridos com sucesso (se não existiam).")

except Exception as e:
    print(f"Erro ao operar no banco de dados: {e}")
    if conn:
        conn.rollback() # Desfaz as alterações em caso de erro
finally:
    if cur:
        cur.close()
    if conn:
        conn.close()
    print("Conexão com o banco de dados fechada.")

