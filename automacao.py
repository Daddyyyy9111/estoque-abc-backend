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

# --- Funções de Log ---
def log(msg: str, level: str = "INFO"):
    """Registra mensagens no console e em um arquivo de log."""
    data_hora = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    linha = f"[{data_hora}] [{level}] {msg}"
    print(linha)
    try:
        with open("log.txt", "a", encoding="utf-8") as f:
            f.write(linha + "\n")
    except Exception as e:
        print(f"Erro ao escrever no arquivo de log: {e}")

# --- Funções de Processamento de E-mail ---
def connect_to_email():
    """Conecta ao servidor de e-mail IMAP."""
    try:
        mail = imaplib.IMAP4_SSL(EMAIL_IMAP_SERVER)
        mail.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        log("Login IMAP bem-sucedido.", "INFO")
        return mail
    except Exception as e:
        log(f"Erro ao conectar ou fazer login no IMAP: {e}", "ERROR")
        return None

def fetch_new_emails(mail, processed_emails):
    """Busca novos e-mails com anexos PDF e retorna os caminhos dos PDFs baixados."""
    mail.select('inbox')
    status, email_ids = mail.search(None, 'UNSEEN', 'HEADER Subject "Pedido CJA"') # Busca apenas e-mails não lidos com o assunto específico
    email_id_list = email_ids[0].split()
    
    new_pdfs = []
    
    log(f"Emails não lidos encontrados: {len(email_id_list)}", "INFO")

    for email_id in email_id_list:
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        for response_part in msg_data:
            if isinstance(response_part, tuple):
                msg = email.message_from_bytes(response_part[1])
                
                # Decodifica o assunto
                subject, encoding = decode_header(msg['Subject'])[0]
                if isinstance(subject, bytes):
                    subject = subject.decode(encoding if encoding else 'utf-8')

                # Verifica se o e-mail já foi processado
                if email_id.decode() in processed_emails:
                    log(f"Email ID {email_id.decode()} (Assunto: {subject}) já foi processado. Pulando.", "INFO")
                    continue

                log(f"Processando email: {subject}", "INFO")

                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue

                    filename = part.get_filename()
                    if filename and filename.endswith('.pdf'):
                        filepath = os.path.join(PDF_FOLDER, filename)
                        os.makedirs(PDF_FOLDER, exist_ok=True)
                        with open(filepath, 'wb') as f:
                            f.write(part.get_payload(decode=True))
                        log(f"PDF baixado: {filepath}", "INFO")
                        new_pdfs.append(filepath)
                        processed_emails.add(email_id.decode()) # Adiciona o ID do e-mail à lista de processados
    return new_pdfs

# --- Funções de Extração de PDF ---
def extract_info_from_pdf(pdf_path):
    """Extrai informações de um PDF de pedido CJA."""
    extracted_items = []
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text()
        doc.close()

        # Regex para extrair OS e data de emissão
        os_match = re.search(r'OS:\s*(\d+)', text, re.IGNORECASE)
        data_emissao_match = re.search(r'Data de Emissão:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        prazo_entrega_match = re.search(r'Prazo de Entrega:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        cidade_destino_match = re.search(r'Cidade de Destino:\s*([A-Za-z\s]+)', text, re.IGNORECASE)

        os_number = os_match.group(1) if os_match else "N/A"
        data_emissao = data_emissao_match.group(1) if data_emissao_match else "N/A"
        prazo_entrega = prazo_entrega_match.group(1) if prazo_entrega_match else "N/A"
        cidade_destino = cidade_destino_match.group(1).strip() if cidade_destino_match else "N/A"

        # Regex para extrair itens de pedido (Modelo CJA, Tipo de Tampo, Quantidade)
        # Ex: "CJA-06  MDF  10" ou "CJA-05  PLASTICO  5"
        # Adicionado para capturar o tipo CJA (ZURICH ou MASTICMOL) se presente
        # Padrão mais robusto para capturar tipo CJA, modelo CJA, tipo de tampo e quantidade
        item_pattern = re.compile(r'(ZURICH|MASTICMOL)?\s*(CJA-\d{2})\s+(MDF|PLASTICO|MASTICMOL)\s+(\d+)', re.IGNORECASE)
        
        for line in text.split('\n'):
            item_match = item_pattern.search(line)
            if item_match:
                tipo_cja = item_match.group(1).upper() if item_match.group(1) else "N/A" # Captura o tipo CJA
                modelo_cja = item_match.group(2).upper()
                tampo_tipo = item_match.group(3).upper()
                quantidade = int(item_match.group(4))
                extracted_items.append({
                    "tipo_cja": tipo_cja,
                    "modelo_cja": modelo_cja,
                    "tampo_tipo": tampo_tipo,
                    "quantidade": quantidade,
                    "os_number": os_number,
                    "cidade_destino": cidade_destino,
                    "data_emissao": data_emissao,
                    "prazo_entrega": prazo_entrega
                })
        log(f"Informações extraídas do PDF {pdf_path}: OS={os_number}, Cidade={cidade_destino}, Itens={len(extracted_items)}", "INFO")
    except Exception as e:
        log(f"Erro ao extrair informações do PDF {pdf_path}: {e}", "ERROR")
    return extracted_items

# --- Funções de Persistência de E-mails Processados ---
def load_processed_emails():
    """Carrega a lista de IDs de e-mails já processados."""
    if os.path.exists(PROCESSED_LIST_FILE):
        with open(PROCESSED_LIST_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_processed_emails(processed_emails):
    """Salva a lista de IDs de e-mails processados."""
    with open(PROCESSED_LIST_FILE, 'w') as f:
        json.dump(list(processed_emails), f)

# --- Funções de Comunicação com o Backend ---
FIREBASE_API_KEY = "AIzaSyA0NNzu5Uuhoq1IYtiIz3QLJZAzywUwd9M" # Sua API Key do Firebase
FIREBASE_EMAIL = "automacao@example.com" # Email do usuário de automação no Firebase
FIREBASE_PASSWORD = "password123" # Senha do usuário de automação no Firebase

auth_token = None

def get_firebase_id_token():
    """Obtém um ID Token do Firebase para autenticação no backend."""
    global auth_token
    if auth_token:
        return auth_token

    try:
        # Endpoint para login com email/senha no Firebase Authentication
        rest_api_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={FIREBASE_API_KEY}"
        payload = json.dumps({
            "email": FIREBASE_EMAIL,
            "password": FIREBASE_PASSWORD,
            "returnSecureToken": True
        })
        headers = {"Content-Type": "application/json"}

        response = requests.post(rest_api_url, data=payload, headers=headers)
        response.raise_for_status()  # Levanta um erro para status de erro HTTP
        
        token_data = response.json()
        auth_token = token_data['idToken']
        log("Token de autenticação Firebase obtido com sucesso.", "INFO")
        return auth_token
    except requests.exceptions.HTTPError as http_err:
        log(f"Erro ao obter token de autenticação Firebase: {response.status_code} {response.reason} for url: {response.url}", "ERROR")
        log(f"Detalhes do erro: {response.text}", "ERROR")
        return None
    except Exception as e:
        log(f"Erro inesperado ao obter token de autenticação Firebase: {e}", "ERROR")
        return None

def update_backend_from_extracted_data(extracted_data):
    """Envia os dados extraídos para o endpoint de pedidos pendentes do backend."""
    if not extracted_data:
        log("Nenhum dado para enviar para o backend.", "INFO")
        return

    token = get_firebase_id_token()
    if not token:
        log("Não foi possível obter o token de autenticação. Pulando o envio para o backend.", "CRITICAL")
        return

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }

    # Agrupa os itens por OS para enviar um pedido por vez
    orders_to_send = {}
    for item in extracted_data:
        os_number = item.get("os_number")
        if os_number not in orders_to_send:
            orders_to_send[os_number] = {
                "os_number": os_number,
                "cidade_destino": item.get("cidade_destino"),
                "data_emissao": item.get("data_emissao"),
                "prazo_entrega": item.get("prazo_entrega"),
                "itens": [],
                "status": "Pendente", # Define o status inicial como Pendente
                "created_by": "automacao" # Define o criador como automacao
            }
        orders_to_send[os_number]["itens"].append({
            "tipo_cja": item.get("tipo_cja"),
            "modelo_cja": item.get("modelo_cja"),
            "tampo_tipo": item.get("tampo_tipo"),
            "quantidade": item.get("quantidade")
        })

    for os_number, order_data in orders_to_send.items():
        try:
            log(f"Enviando pedido OS {os_number} para o backend...", "INFO")
            response = requests.post(f"{API_BACKEND_URL}/pedidos_pendentes", json=order_data, headers=headers)
            response.raise_for_status()  # Levanta um erro para status de erro HTTP
            log(f"Pedido OS {os_number} enviado com sucesso. Resposta: {response.json()}", "INFO")
        except requests.exceptions.HTTPError as http_err:
            log(f"Erro HTTP ao enviar pedido OS {os_number}: {response.status_code} {response.reason}", "ERROR")
            log(f"Detalhes do erro: {response.text}", "ERROR")
        except Exception as e:
            log(f"Erro inesperado ao enviar pedido OS {os_number}: {e}", "ERROR")

# --- Função Principal ---
def main():
    log("=== Iniciando o automatizador de Pedidos ABC Móveis ===", "INFO")
    
    # Carrega a lista de e-mails já processados do arquivo
    processed_emails = load_processed_emails()
    log(f"Carregados {len(processed_emails)} itens de pedido da lista de processados.", "INFO")

    # Tenta obter o token de autenticação uma vez no início
    initial_token = get_firebase_id_token()
    if not initial_token:
        log("Não foi possível obter o token de autenticação inicial. O script pode falhar ao enviar pedidos.", "CRITICAL")

    while True:
        log("\n==== Início do Ciclo de Verificação de Pedidos ====", "INFO")
        log("Iniciando busca por novos emails e PDFs...", "INFO")
        
        mail = connect_to_email()
        if mail:
            new_pdfs = fetch_new_emails(mail, processed_emails)
            save_processed_emails(processed_emails) # CORRIGIDO: Usando processed_emails
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
        time.sleep(10) # Espera 10 segundos antes do próximo ciclo (ajuste conforme necessário)

if __name__ == '__main__':
    main()
