import imaplib
import email
from email.header import decode_header
import os
import re
import fitz # PyMuPDF
from datetime import datetime, timedelta
import json
import time
import requests # Importa a biblioteca requests para fazer requisições HTTP

# --- Configurações de E-mail ---
EMAIL_IMAP_SERVER = 'imap.gmail.com'
EMAIL_ADDRESS = 'producao.abcmoveis@gmail.com' # <--- ALtere para o seu e-mail
EMAIL_PASSWORD = 'rclocqgyhkvaqhae' # <--- ALtere para sua senha de app (ou senha normal se não usar 2FA)

# --- Configurações de Pasta ---
PDF_FOLDER = './Pedidos_PDF'
PROCESSED_LIST_FILE = 'processed_emails.json'

# --- Configuração da API do Backend ---
# URL base do seu backend no Render.com
API_BACKEND_URL = 'https://estoque-abc-frontend.onrender.com' # Verifique se esta é a URL correta do seu backend

# --- Configurações do Firebase Auth para Automação ---
# Você pode encontrar esta API Key no Firebase Console -> Project settings -> General -> Web API Key
FIREBASE_API_KEY = "AIzaSyA0NNzu5Uuhoq1IYtiIz3QLJZAzywUwd9M" # <--- SUBSTITUA PELA SUA CHAVE DE API REAL DO FIREBASE
AUTOMATION_EMAIL = "automacao@example.com" # Email do usuário de automação criado no backend
AUTOMATION_PASSWORD = "auto123" # Senha do usuário de automação

# Variável global para armazenar o token de autenticação
AUTH_TOKEN = None

# --- Funções de Log ---
def log(msg: str, level: str = "INFO"):
    """Registra mensagens no console e em um arquivo de log."""
    data_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linha = f"[{data_hora}] [{level}] {msg}"
    print(linha)
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except IOError as e:
        print(f"[{data_hora}] [ERROR] Erro ao escrever no arquivo de log: {e}")

# --- Funções de Gerenciamento de Arquivos ---
def ensure_pdf_folder_exists():
    """Garante que a pasta para salvar PDFs exista."""
    if not os.path.exists(PDF_FOLDER):
        os.makedirs(PDF_FOLDER)
        log(f"Pasta de PDFs '{PDF_FOLDER}' verificada/criada.", "INFO")

def load_processed_emails():
    """Carrega a lista de IDs de emails já processados."""
    if os.path.exists(PROCESSED_LIST_FILE):
        with open(PROCESSED_LIST_FILE, 'r', encoding='utf-8') as f:
            processed_list = json.load(f)
        log(f"Carregados {len(processed_list)} itens de pedido da lista de processados.", "INFO")
        return set(processed_list)
    return set()

def save_processed_emails(processed_list: set):
    """Salva a lista atualizada de IDs de emails processados."""
    with open(PROCESSED_LIST_FILE, 'w', encoding='utf-8') as f:
        json.dump(list(processed_list), f, indent=4)
    log(f"Lista de emails processados salva. Total: {len(processed_list)}", "INFO")

# --- Funções de E-mail ---
def connect_to_email():
    """Conecta ao servidor IMAP e faz login."""
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        log(f"Conectando ao servidor IMAP: {EMAIL_IMAP_SERVER}", "INFO")
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        log("Login IMAP bem-sucedido.", "INFO")
        return mail
    except Exception as e:
        log(f"Erro ao conectar ou fazer login no email: {e}", "CRITICAL")
        return None

def fetch_new_emails(mail, processed_list: set):
    """Busca novos emails e baixa PDFs de anexos que contêm 'PEDIDO' no nome do arquivo."""
    new_pdfs_downloaded = []
    try:
        mail.select('inbox')
        status, email_ids = mail.search(None, 'UNSEEN') # Busca emails não lidos
        
        if status != 'OK':
            log(f"Erro ao buscar emails: {status}", "ERROR")
            return new_pdfs_downloaded

        email_id_list = [uid.decode('utf-8') for uid in email_ids[0].split()]
        log(f"Emails não lidos encontrados: {len(email_id_list)}", "INFO")

        for email_id_str in email_id_list:
            if email_id_str in processed_list:
                log(f"Email ID {email_id_str} já processado, pulando.", "INFO")
                continue

            status, msg_data = mail.fetch(email_id_str.encode('utf-8'), '(RFC822)')
            if status != 'OK':
                log(f"Erro ao buscar email ID {email_id_str}: {status}", "ERROR")
                continue

            raw_email = msg_data[0][1]
            msg = email.message_from_bytes(raw_email)

            # Decodificar o assunto
            subject, encoding = decode_header(msg['Subject'])[0]
            if isinstance(subject, bytes):
                subject = subject.decode(encoding if encoding else 'utf-8')
            log(f"Processando email ID {email_id_str} - Assunto: '{subject}'", "INFO")

            for part in msg.walk():
                if part.get_content_maintype() == 'multipart':
                    continue
                if part.get('Content-Disposition') is None:
                    continue

                filename = part.get_filename()
                if filename:
                    decoded_filename, charset = decode_header(filename)[0]
                    if isinstance(decoded_filename, bytes):
                        filename = decoded_filename.decode(charset if charset else 'utf-8')

                    # AQUI: Verificação para "PEDIDO" no nome do arquivo
                    if filename.lower().endswith('.pdf') and "pedido" in filename.lower():
                        filepath = os.path.join(PDF_FOLDER, filename)
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        log(f"PDF salvo (contém 'PEDIDO'): {filename} em {filepath}", "INFO")
                        new_pdfs_downloaded.append(filepath)
                    else:
                        log(f"PDF '{filename}' não contém 'PEDIDO' no nome ou não é um PDF. Ignorando.", "INFO")
            
            # Marcar email como lido após processar
            mail.store(email_id_str.encode('utf-8'), '+FLAGS', '\\Seen')
            log(f"Email ID {email_id_str} marcado como lido.", "INFO")
            processed_list.add(email_id_str) # Adiciona à lista de processados

    except Exception as e:
        log(f"Erro durante a busca ou download de emails: {e}", "ERROR")
    finally:
        mail.logout()
    return new_pdfs_downloaded

# --- Funções de Extração de PDF ---
def extract_info_from_pdf(pdf_path: str):
    """
    Extrai informações de OS, Modelo, Quantidade e Tipo de Tampo de um PDF.
    Assume que o PDF já foi filtrado pelo nome do arquivo ('PEDIDO').
    """
    extracted_data = []
    try:
        doc = fitz.open(pdf_path)
        log(f"Analisando PDF: {os.path.basename(pdf_path)} ({doc.page_count} páginas)", "INFO")

        os_number = "N/A"
        cidade_destino = "N/A"

        for page_num in range(doc.page_count):
            page = doc.load_page(page_num)
            text = page.get_text("text")
            log(f"DEBUG: Texto completo da página {page_num + 1} de '{os.path.basename(pdf_path)}':\n---\n{text}\n---", "DEBUG")

            # Extrair número da OS e Cidade de Destino (se não encontrados ainda)
            if os_number == "N/A":
                os_match = re.search(r'OS\s*[:]?\s*(\d+)', text, re.IGNORECASE)
                if os_match:
                    os_number = os_match.group(1).strip()
            
            if cidade_destino == "N/A":
                cidade_match = re.search(r'CIDADE\s*[:]?\s*([A-Z\s\/]+)', text, re.IGNORECASE)
                if cidade_match:
                    cidade_destino = cidade_match.group(1).strip()

            lines = text.split('\n')
            
            # Variável para armazenar a quantidade da linha anterior
            current_qty = None

            for i, line in enumerate(lines):
                line = line.strip()
                log(f"DEBUG: Analisando linha {i+1}: '{line}'", "DEBUG")

                # Tenta extrair a quantidade se a linha contiver apenas números
                qty_match = re.match(r'^\s*(\d+)\s*$', line)
                if qty_match:
                    current_qty = int(qty_match.group(1))
                    log(f"DEBUG: Quantidade numérica identificada: {current_qty}", "DEBUG")
                    continue # Vai para a próxima linha para procurar a descrição

                # Tenta extrair a descrição do produto se uma quantidade foi identificada na linha anterior
                # e a linha atual contém um modelo CJA (APENAS CJA)
                if current_qty is not None:
                    # Regex para CJA (APENAS CJA) com ou sem tampo
                    # Ajustado para capturar CJA-XX e opcionalmente a letra (Grupo 1)
                    product_description_match = re.search(
                        r'''
                        (?:CONJUNTO\s+(?:ALUNO|INDIVIDUAL\s+PARA\s+ALUNO)\s+)? # "CONJUNTO ALUNO/INDIVIDUAL PARA ALUNO " (opcional)
                        (CJA-(?:03|04|05|06)[A-Z]?)\s* # Grupo 1: Modelo CJA específico (CJA-03, CJA-04, etc. com letra opcional)
                        (?:.*? # Não captura, apenas avança
                        \(TAMPO\s+ # "(TAMPO "
                        (B|MDF|PL[AÁ]STICO) # Grupo 2: Tipo de tampo (B, MDF, PLASTICO/PLÁSTICO)
                        \))? # Tampo é opcional
                        ''',
                        line, re.IGNORECASE | re.VERBOSE
                    )
                    
                    if product_description_match:
                        full_modelo = product_description_match.group(1).upper() # Ex: CJA-03B
                        tampo = product_description_match.group(2) # Grupo 2 é o tipo de tampo (pode ser None)
                        
                        # --- NORMALIZAÇÃO DO MODELO CJA ---
                        # Remove qualquer letra no final do modelo CJA (ex: CJA-03B -> CJA-03)
                        modelo = re.sub(r'([A-Z]{3}-\d+)[A-Z]?$', r'\1', full_modelo)
                        log(f"DEBUG: Modelo '{full_modelo}' normalizado para '{modelo}'", "DEBUG")
                        # --- FIM DA NORMALIZAÇÃO ---

                        if tampo:
                            tampo = tampo.upper()
                            if 'PLÁSTICO' in tampo:
                                tampo = 'PLASTICO'
                            elif tampo == 'B': # Se 'B' significa Masticmol, normalize
                                tampo = 'MASTICMOL'
                        else:
                            tampo = "N/A" # Se não encontrou tampo, define como N/A

                        # Determinar tipo CJA (ZURICH ou MASTICMOL) - se não estiver no PDF, pode ser inferido ou padrão
                        tipo_cja = "ZURICH" # Padrão
                        if tampo == "MASTICMOL":
                            tipo_cja = "MASTICMOL"


                        if modelo and current_qty > 0:
                            extracted_data.append({
                                'os_number': os_number, # Renomeado para 'os_number' para corresponder ao backend
                                'cidade_destino': cidade_destino,
                                'tipo_cja': tipo_cja, # Adicionado tipo_cja
                                'modelo_cja': modelo, # Renomeado para 'modelo_cja'
                                'tampo_tipo': tampo, # Renomeado para 'tampo_tipo'
                                'quantidade': current_qty,
                                'pdf_filename': os.path.basename(pdf_path)
                            })
                            log(f"INFO: Item de pedido CJA encontrado no PDF '{os.path.basename(pdf_path)}' (Pág {page_num + 1}): Tipo CJA '{tipo_cja}', Modelo Normalizado '{modelo}', Quantidade '{current_qty}', Tampo: '{tampo}'", "INFO")
                        current_qty = None # Reseta a quantidade após o uso
                    else:
                        # Se a linha não é uma descrição de produto CJA válida, a quantidade anterior é irrelevante
                        current_qty = None
        doc.close()
    except Exception as e:
        log(f"Erro ao extrair informações de {os.path.basename(pdf_path)}: {e}", "ERROR")
    return extracted_data

# --- Funções de Autenticação Firebase ---
def get_firebase_id_token():
    """
    Obtém um ID Token do Firebase Authentication usando as credenciais do usuário de automação.
    """
    global AUTH_TOKEN
    if AUTH_TOKEN:
        # Em um cenário real, você verificaria a expiração do token aqui
        # e o renovaria se necessário. Para simplicidade, vamos tentar obter um novo a cada ciclo
        # ou apenas usar o existente se já tiver sido obtido.
        log("Token de autenticação já existe, reutilizando.", "INFO")
        return AUTH_TOKEN

    log(f"Obtendo novo token de autenticação para {AUTOMATION_EMAIL}...", "INFO")
    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
    payload = json.dumps({
        "email": AUTOMATION_EMAIL,
        "password": AUTOMATION_PASSWORD,
        "returnSecureToken": True
    })
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post(auth_url, data=payload, headers=headers)
        response.raise_for_status() # Lança um erro para status HTTP 4xx/5xx
        AUTH_TOKEN = response.json()['idToken']
        log("Token de autenticação Firebase obtido com sucesso.", "INFO")
        return AUTH_TOKEN
    except requests.exceptions.RequestException as e:
        log(f"Erro ao obter token de autenticação Firebase: {e}", "ERROR")
        AUTH_TOKEN = None
        return None
    except Exception as e:
        log(f"Erro inesperado ao obter token de autenticação: {e}", "ERROR")
        AUTH_TOKEN = None
        return None

# --- Funções de Atualização do Backend (API Flask) ---
def send_order_to_backend(order_data: dict):
    """
    ENVIA OS DADOS DE UM PEDIDO PARA O BACKEND FLASK PARA CRIAR UM PEDIDO PENDENTE.
    NÃO DEDUZ ESTOQUE NESTA ETAPA.
    """
    global AUTH_TOKEN
    if not AUTH_TOKEN:
        log("Nenhum token de autenticação disponível. Tentando obter um.", "WARNING")
        AUTH_TOKEN = get_firebase_id_token()
        if not AUTH_TOKEN:
            log("Falha ao obter token de autenticação, não é possível enviar o pedido.", "ERROR")
            return

    endpoint = f"{API_BACKEND_URL}/pedidos_pendentes" # ENDPOINT CORRETO PARA CRIAR PEDIDOS PENDENTES
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {AUTH_TOKEN}" # Inclui o token de autenticação
    }

    try:
        # Adiciona um campo para indicar que a requisição é da automação, se necessário
        order_data['registrado_por'] = 'Sistema de Automação' 
        response = requests.post(endpoint, json=order_data, headers=headers)
        response.raise_for_status() # Lança um erro para status HTTP 4xx/5xx
        log(f"Pedido pendente enviado com sucesso para o backend. Resposta: {response.json()}", "INFO")
    except requests.exceptions.HTTPError as http_err:
        log(f"Erro HTTP ao enviar pedido pendente: {http_err.response.status_code} - {http_err.response.text}", "ERROR")
        if http_err.response.status_code == 401:
            log("Token de autenticação pode estar expirado ou inválido. Forçando renovação.", "WARNING")
            AUTH_TOKEN = None # Invalida o token para forçar uma nova tentativa de login
    except requests.exceptions.RequestException as e:
        log(f"Erro de conexão ao enviar pedido pendente para o backend: {e}", "ERROR")
    except Exception as e:
        log(f"Erro inesperado ao enviar pedido pendente: {e}", "ERROR")

def update_backend_from_extracted_data(all_extracted_items: list):
    """
    Prepara os dados extraídos e os envia para o backend.
    """
    if not all_extracted_items:
        log("Nenhum item de pedido para processar.", "INFO")
        return

    log(f"Encontrados {len(all_extracted_items)} ITENS DE PEDIDO para processar no backend.", "INFO")

    # Agrupar itens por OS para enviar um pedido completo por vez
    orders_to_process = {}
    for item in all_extracted_items:
        os_num = item['os_number']
        if os_num not in orders_to_process:
            orders_to_process[os_num] = {
                'os_number': os_num,
                'cidade_destino': item['cidade_destino'],
                'itens': []
            }
        orders_to_process[os_num]['itens'].append({
            'tipo_cja': item['tipo_cja'], # Adicionado
            'modelo_cja': item['modelo_cja'], # Renomeado
            'tampo_tipo': item['tampo_tipo'], # Renomeado
            'quantidade': item['quantidade']
        })
    
    for os_num, order_data in orders_to_process.items():
        log(f"Enviando Pedido OS {os_num} para o backend (criar pedido pendente)...", "INFO")
        send_order_to_backend(order_data)


def main():
    log("=== Iniciando o automatizador de Pedidos ABC Móveis ===", "INFO")
    ensure_pdf_folder_exists()
    processed_emails = load_processed_emails() 

    # Tenta obter o token de autenticação logo no início
    global AUTH_TOKEN
    AUTH_TOKEN = get_firebase_id_token()
    if not AUTH_TOKEN:
        log("Não foi possível obter o token de autenticação inicial. O script pode falhar ao enviar pedidos.", "CRITICAL")

    while True:
        log("\n==== Início do Ciclo de Verificação de Pedidos ====", "INFO")
        log("Iniciando busca por novos emails e PDFs...", "INFO")
        
        mail = connect_to_email()
        if mail:
            new_pdfs = fetch_new_emails(mail, processed_emails)
            save_processed_emails(processed_list) 
            log(f"Novos PDFs baixados neste ciclo: {len(new_pdfs)}", "INFO")
            
            if new_pdfs:
                log("Iniciando extração de informações dos PDFs recém-baixados...", "INFO")
                all_extracted_items = []
                for pdf_path in new_pdfs:
                    extracted_from_pdf = extract_info_from_pdf(pdf_path)
                    all_extracted_items.extend(extracted_from_pdf)
                
                log(f"Total de novos ITENS DE PEDIDO CJA extraídos dos PDFs baixados neste ciclo: {len(all_extracted_items)}", "INFO")
                
                # Chamada para enviar os dados para o backend
                update_backend_from_extracted_data(all_extracted_items)
            else:
                log("Nenhum novo PDF para processar neste ciclo.", "INFO")
        else:
            log("Não foi possível conectar ao email. Tentando novamente no próximo ciclo.", "WARNING")

        log("==== Ciclo de Verificação Concluído. Aguardando próximo ciclo... ====", "INFO")
        time.sleep(10) # Espera 10 segundos antes do próximo ciclo

if __name__ == "__main__":
    main()
