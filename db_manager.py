import psycopg2
import os
from datetime import datetime

# --- Configurações de Log ---
def log(msg: str, level: str = "INFO"):
    """Registra mensagens no console e em um arquivo de log."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_message = f"[{timestamp}] [{level}] [DB_MANAGER] {msg}"
    print(log_message)
    # Opcional: Salvar em arquivo de log
    # with open("automacao.log", "a", encoding="utf-8") as f:
    #     f.write(log_message + "\n")

# --- Configurações do Banco de Dados ---
# Obtém as variáveis de ambiente ou usa valores padrão
DB_NAME = os.environ.get('DB_NAME', 'estoque_abc') # Nome do banco de dados
DB_USER = os.environ.get('DB_USER', 'postgres') # Usuário do banco de dados
# ATENÇÃO: Senha hardcoded para depuração. Não recomendado para produção!
DB_PASSWORD = '12345678' # <--- MUDANÇA AQUI: Senha definida diretamente
DB_HOST = os.environ.get('DB_HOST', 'localhost') # Host do banco de dados
DB_PORT = os.environ.get('DB_PORT', '5432') # Porta do banco de dados

def get_db_connection():
    """
    Estabelece e retorna uma conexão com o banco de dados PostgreSQL.
    Retorna o objeto de conexão ou None em caso de erro.
    """
    conn = None
    try:
        # Tenta conectar ao banco de dados usando os parâmetros nomeados
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            client_encoding='UTF8'
        )
        log(f"Conexão com o banco de dados '{DB_NAME}' estabelecida com sucesso.", "INFO")
    except psycopg2.OperationalError as e:
        # Captura erros operacionais (ex: senha incorreta, banco de dados não existe)
        log(f"Erro operacional ao conectar ao banco de dados: {e}", "CRITICAL")
        log(f"Detalhes: DB_NAME='{DB_NAME}', DB_USER='{DB_USER}', DB_PASSWORD_REPR='{DB_PASSWORD}'", "CRITICAL")
        conn = None
    except Exception as e:
        # Captura outros erros inesperados
        log(f"Erro inesperado ao conectar ao banco de dados: {e}", "CRITICAL")
        log(f"Detalhes: DB_NAME='{DB_NAME}', DB_USER='{DB_USER}', DB_PASSWORD_REPR='{DB_PASSWORD}'", "CRITICAL")
        conn = None
    return conn

# Adicionando esta função para compatibilidade com chamadas antigas em automacao.py
def connect_db():
    """
    Função de compatibilidade que chama get_db_connection.
    """
    return get_db_connection()

def create_tables():
    """
    Cria as tabelas necessárias no banco de dados, se ainda não existirem.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            log("Verificando/Criando tabela 'estoque_atual'...", "INFO")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS estoque_atual (
                    modelo VARCHAR(50) PRIMARY KEY,
                    quantidade INTEGER NOT NULL,
                    tampo VARCHAR(50)
                );
            """)
            log("Tabela 'estoque_atual' verificada/criada com sucesso.", "INFO")

            log("Verificando/Criando tabela 'pedidos_processados'...", "INFO")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS pedidos_processados (
                    id SERIAL PRIMARY KEY,
                    os VARCHAR(50) NOT NULL,
                    cliente VARCHAR(255),
                    cidade VARCHAR(255),
                    data_emissao DATE,
                    prazo_entrega DATE,
                    pdf_filename VARCHAR(255),
                    data_processamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            log("Tabela 'pedidos_processados' verificada/criada com sucesso.", "INFO")

            log("Verificando/Criando tabela 'itens_pedido'...", "INFO")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS itens_pedido (
                    id SERIAL PRIMARY KEY,
                    pedido_id INTEGER REFERENCES pedidos_processados(id),
                    modelo VARCHAR(50) NOT NULL,
                    quantidade INTEGER NOT NULL,
                    tampo VARCHAR(50)
                );
            """)
            log("Tabela 'itens_pedido' verificada/criada com sucesso.", "INFO")

            conn.commit()
            cur.close()
        except Exception as e:
            log(f"Não foi possível criar tabelas: {e}", "ERROR")
            conn.rollback()
        finally:
            conn.close()
    else:
        log("Não foi possível criar tabelas: conexão com o banco de dados falhou.", "ERROR")

def update_estoque(modelo: str, quantidade: int, tampo: str):
    """
    Atualiza a quantidade de um item no estoque ou o insere se não existir.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            log(f"Atualizando/Inserindo estoque para Modelo='{modelo}', Qtd='{quantidade}', Tampo: '{tampo}'", "INFO")
            cur.execute("""
                INSERT INTO estoque_atual (modelo, quantidade, tampo)
                VALUES (%s, %s, %s)
                ON CONFLICT (modelo) DO UPDATE
                SET quantidade = estoque_atual.quantidade + EXCLUDED.quantidade,
                    tampo = EXCLUDED.tampo;
            """, (modelo, quantidade, tampo))
            conn.commit()
            log(f"Estoque para '{modelo}' atualizado com sucesso.", "INFO")
            cur.close()
        except Exception as e:
            log(f"Erro ao atualizar estoque para '{modelo}': {e}", "ERROR")
            conn.rollback()
        finally:
            conn.close()
    else:
        log("Não foi possível conectar ao banco de dados para atualizar estoque.", "ERROR")

def add_pedido_and_itens(os_num: str, cliente: str, cidade: str, data_emissao: str, prazo_entrega: str, pdf_filename: str, itens: list):
    """
    Adiciona um novo pedido e seus itens ao banco de dados.
    """
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            log(f"Adicionando Pedido OS: {os_num} - Cliente: {cliente}...", "INFO")

            # Insere o pedido principal
            cur.execute("""
                INSERT INTO pedidos_processados (os, cliente, cidade, data_emissao, prazo_entrega, pdf_filename)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (os_num, cliente, cidade, data_emissao, prazo_entrega, pdf_filename))
            pedido_id = cur.fetchone()[0]
            log(f"Pedido OS {os_num} adicionado com ID: {pedido_id}", "INFO")

            # Insere os itens do pedido
            for item in itens:
                log(f"Adicionando item ao pedido {pedido_id}: Modelo='{item['modelo']}', Qtd='{item['quantidade']}', Tampo: '{item['tampo']}'", "INFO")
                cur.execute("""
                    INSERT INTO itens_pedido (pedido_id, modelo, quantidade, tampo)
                    VALUES (%s, %s, %s, %s);
                """, (pedido_id, item['modelo'], item['quantidade'], item['tampo']))
            log(f"Todos os itens adicionados ao Pedido {pedido_id}.", "INFO")

            conn.commit()
            cur.close()
        except Exception as e:
            log(f"Erro ao adicionar pedido e itens para OS {os_num}: {e}", "ERROR")
            conn.rollback()
        finally:
            conn.close()
    else:
        log(f"Não foi possível conectar ao banco de dados para adicionar pedido OS {os_num}.", "ERROR")

def get_all_estoque():
    """
    Retorna todos os itens do estoque atual.
    """
    conn = get_db_connection()
    estoque = []
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT modelo, quantidade, tampo FROM estoque_atual;")
            estoque = cur.fetchall()
            cur.close()
        except Exception as e:
            log(f"Erro ao buscar estoque: {e}", "ERROR")
        finally:
            conn.close()
    return estoque

def get_processed_orders_os():
    """
    Retorna uma lista de números de OS de pedidos já processados.
    """
    conn = get_db_connection()
    os_list = []
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT os FROM pedidos_processados;")
            os_list = [row[0] for row in cur.fetchall()]
            cur.close()
        except Exception as e:
            log(f"Erro ao buscar pedidos processados: {e}", "ERROR")
        finally:
            conn.close()
    return os_list

def get_model_id(model_name: str):
    """
    Função placeholder para obter o ID de um modelo.
    Por enquanto, retorna None. Pode ser implementada para buscar em uma tabela de modelos.
    """
    log(f"Chamada para get_model_id para o modelo: {model_name}. Esta função é um placeholder.", "INFO")
    # Implementação futura: buscar o ID do modelo no banco de dados
    return None

def get_component_id(component_name: str):
    """
    Função placeholder para obter o ID de um componente.
    Por enquanto, retorna None. Pode ser implementada para buscar em uma tabela de componentes.
    """
    log(f"Chamada para get_component_id para o componente: {component_name}. Esta função é um placeholder.", "INFO")
    # Implementação futura: buscar o ID do componente no banco de dados
    return None
