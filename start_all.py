import subprocess
import time
import re
import os
import sys
import webbrowser
from datetime import datetime

# --- Configurações ---
FLASK_APP_PATH = os.path.join(os.path.dirname(__file__), 'backend_app.py')
NGROK_EXE_PATH = os.path.join(os.path.dirname(__file__), 'ngrok.exe') # Assumindo ngrok.exe está na mesma pasta
FLASK_PORT = 5000
FRONTEND_HTML_PATH = os.path.join(os.path.dirname(__file__), 'estoque.html') # Ou 'index.html' se você renomeou

# --- Funções de Log (para este script) ---
def log(msg: str, level: str = "INFO"):
    """Registra mensagens no console."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] [START_ALL] [{level}] {msg}")

def find_ngrok_url(output: str) -> str | None:
    """Extrai a URL HTTPS do output do ngrok."""
    # Regex para encontrar a URL https://...
    match = re.search(r'https://[a-zA-Z0-9.-]+\.ngrok-free\.app', output)
    if match:
        return match.group(0)
    return None

def update_html_with_ngrok_url(html_file_path: str, ngrok_url: str):
    """Atualiza a API_BASE_URL no arquivo HTML."""
    try:
        with open(html_file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Regex para encontrar e substituir a linha API_BASE_URL
        # Garante que não haja espaços antes do https://
        new_content = re.sub(
            r"const API_BASE_URL = 'https?:\/\/[a-zA-Z0-9.-]+(\.ngrok-free\.app)?[\/a-zA-Z0-9]*';",
            f"const API_BASE_URL = '{ngrok_url}';",
            content
        )

        if new_content == content:
            log("AVISO: API_BASE_URL não encontrada ou não atualizada no HTML. Verifique o regex.", "WARNING")
        else:
            with open(html_file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            log(f"'{FRONTEND_HTML_PATH}' atualizado com a URL do ngrok: {ngrok_url}", "INFO")

    except FileNotFoundError:
        log(f"ERRO: Arquivo HTML '{html_file_path}' não encontrado.", "CRITICAL")
        sys.exit(1)
    except Exception as e:
        log(f"ERRO ao atualizar o arquivo HTML: {e}", "CRITICAL")
        sys.exit(1)

def main():
    log("Iniciando o automatizador de ambiente...")

    # 1. Iniciar o servidor Flask em um processo separado
    log(f"Iniciando servidor Flask em {FLASK_APP_PATH} na porta {FLASK_PORT}...")
    # Usamos shell=True no Windows para que o python.exe seja encontrado no venv
    flask_process = subprocess.Popen([sys.executable, FLASK_APP_PATH], shell=True)
    time.sleep(5) # Dá um tempo para o Flask iniciar

    # 2. Iniciar o ngrok e capturar a URL
    log(f"Iniciando ngrok em {NGROK_EXE_PATH} para a porta {FLASK_PORT}...")
    # Redireciona stdout e stderr para PIPE para capturar a saída
    ngrok_process = subprocess.Popen([NGROK_EXE_PATH, 'http', str(FLASK_PORT)],
                                     stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     text=True, bufsize=1, universal_newlines=True)

    ngrok_url = None
    # Lê a saída do ngrok linha por linha para encontrar a URL
    for line in ngrok_process.stdout:
        log(f"ngrok output: {line.strip()}", "DEBUG") # Loga a saída do ngrok para depuração
        ngrok_url = find_ngrok_url(line)
        if ngrok_url:
            log(f"URL do ngrok encontrada: {ngrok_url}", "INFO")
            break
        # Adiciona um timeout para não ficar preso se ngrok não gerar a URL esperada
        if time.time() - start_time > 30: # 30 segundos de timeout
            log("ERRO: Tempo limite excedido para obter a URL do ngrok.", "CRITICAL")
            ngrok_process.terminate()
            flask_process.terminate()
            sys.exit(1)
    
    if not ngrok_url:
        log("ERRO: Não foi possível obter a URL do ngrok. Verifique se o ngrok está funcionando corretamente.", "CRITICAL")
        ngrok_process.terminate()
        flask_process.terminate()
        sys.exit(1)

    # 3. Atualizar o arquivo HTML com a URL do ngrok
    update_html_with_ngrok_url(FRONTEND_HTML_PATH, ngrok_url)

    # 4. Abrir o arquivo HTML no navegador
    log(f"Abrindo o frontend local em {FRONTEND_HTML_PATH} no navegador...", "INFO")
    webbrowser.open(f'file:///{os.path.abspath(FRONTEND_HTML_PATH)}')

    log("Configuração concluída. Os processos do Flask e ngrok estão rodando.", "INFO")
    log("Pressione Ctrl+C para parar todos os processos.", "INFO")

    try:
        # Mantém o script principal rodando para que os subprocessos continuem
        flask_process.wait()
        ngrok_process.wait()
    except KeyboardInterrupt:
        log("Detectado Ctrl+C. Encerrando processos...", "INFO")
    finally:
        if flask_process.poll() is None: # Se o Flask ainda estiver rodando
            flask_process.terminate()
            log("Servidor Flask encerrado.", "INFO")
        if ngrok_process.poll() is None: # Se o ngrok ainda estiver rodando
            ngrok_process.terminate()
            log("Ngrok encerrado.", "INFO")
        log("Todos os processos encerrados.", "INFO")

if __name__ == '__main__':
    start_time = time.time() # Inicia o contador de tempo
    main()
