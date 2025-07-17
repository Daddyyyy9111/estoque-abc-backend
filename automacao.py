import imaplib
import email # Importa o módulo email completo
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
# ATENÇÃO: SUBSTITUA ESTA URL PELA URL REAL DO SEU SERVIÇO DE BACKEND NO RENDER.COM
API_BACKEND_URL = 'https://estoque-abc-frontend.onrender.com' # <--- ATUALIZE ESTA URL!

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
    
    # --- BUSCA SOMENTE E-MAILS NÃO LIDOS COM "OS" NO ASSUNTO ---
    # Usamos 'SUBJECT', '"OS"' para uma busca IMAP mais geral e depois filtramos com regex no Python.
    status, email_ids = mail.search(None, 'UNSEEN', 'SUBJECT', '"OS"') 

    if status != 'OK':
        log(f"Erro ao buscar emails: {status}", "ERROR")
        return []

    email_id_list = email_ids[0].split()
    email_id_list.reverse() # Processar dos mais antigos para os mais novos

    new_pdfs = []
    
    log(f"Emails NÃO LIDOS encontrados com 'OS' no assunto: {len(email_id_list)}", "INFO")

    # Regex para verificar se o assunto contém "OS" seguido de um número
    os_subject_pattern = re.compile(r'os\s*\d+', re.IGNORECASE)

    for email_id in email_id_list:
        status, msg_data = mail.fetch(email_id, '(RFC822)')
        if status != 'OK':
            log(f"Erro ao buscar dados do email ID {email_id.decode()}: {status}", "ERROR")
            continue

        for response_part in msg_data:
            if isinstance(response_part, tuple):
                # --- CORREÇÃO AQUI: email.message_from_bytes() ---
                msg = email.message_from_bytes(response_part[1])
                
                # Decodifica o assunto
                subject_decoded, encoding = decode_header(msg['Subject'])[0]
                if isinstance(subject_decoded, bytes):
                    subject_decoded = subject_decoded.decode(encoding if encoding else 'utf-8')
                
                # Normaliza o assunto para comparação (remove espaços extras, torna minúsculas)
                normalized_subject = subject_decoded.strip().lower()

                log(f"Verificando email ID {email_id.decode()} - Assunto: '{subject_decoded}' (Normalizado: '{normalized_subject}')", "INFO")

                # Verifica se o assunto corresponde ao padrão 'OS [número]'
                if not os_subject_pattern.search(normalized_subject):
                    log(f"Email ID {email_id.decode()} (Assunto: '{subject_decoded}') não corresponde ao padrão 'OS [número]'. Pulando.", "INFO")
                    # Se não corresponde ao padrão, não deve ser marcado como lido ou processado
                    continue

                # Verifica se o e-mail já foi processado (redundância, mas garante que não há duplicação)
                if email_id.decode() in processed_emails:
                    log(f"Email ID {email_id.decode()} (Assunto: {subject_decoded}) já foi processado. Pulando.", "INFO")
                    continue

                log(f"Processando email: {subject_decoded}", "INFO")

                has_pdf_attachment = False
                for part in msg.walk():
                    if part.get_content_maintype() == 'multipart':
                        continue
                    if part.get('Content-Disposition') is None:
                        continue

                    filename = part.get_filename()
                    if filename and filename.lower().endswith('.pdf'):
                        # --- VERIFICAÇÃO: FILTRAR POR NOMES DE PDF QUE CONTÊM "PEDIDO" ---
                        if "pedido" in filename.lower():
                            filepath = os.path.join(PDF_FOLDER, filename)
                            os.makedirs(PDF_FOLDER, exist_ok=True)
                            with open(filepath, 'wb') as f:
                                f.write(part.get_payload(decode=True))
                            log(f"PDF 'PEDIDO' baixado: {filepath}", "INFO")
                            new_pdfs.append(filepath)
                            has_pdf_attachment = True
                            break # Baixa apenas o primeiro PDF "PEDIDO" encontrado por email
                        else:
                            log(f"Anexo PDF '{filename}' não contém 'PEDIDO' no nome. Pulando.", "INFO")
                    else:
                        log(f"Anexo '{filename}' não é um PDF ou não tem nome. Pulando.", "DEBUG")
                            
                if has_pdf_attachment:
                    processed_emails.add(email_id.decode()) # Adiciona o ID do e-mail à lista de processados
                    # --- MARCA O E-MAIL COMO LIDO NO SERVIDOR IMAP ---
                    mail.store(email_id, '+FLAGS', '\\Seen')
                    log(f"Email ID {email_id.decode()} marcado como LIDO.", "INFO")
                else:
                    log(f"Email ID {email_id.decode()} (Assunto: {subject_decoded}) não contém anexo PDF 'PEDIDO'. Pulando.", "INFO")

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

        log(f"Texto extraído do PDF {pdf_path}:\n---INÍCIO DO TEXTO---\n{text}\n---FIM DO TEXTO---", "INFO") 

        # Regex para extrair OS
        os_match = re.search(r'OS:\s*(\d+)', text, re.IGNORECASE)
        os_number = os_match.group(1) if os_match else "N/A"
        log(f"DEBUG: OS extraída: {os_number}", "DEBUG")

        # Regex para extrair Data de Emissão
        data_emissao_match = re.search(r'DATA DE EMISSÃO:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        data_emissao = data_emissao_match.group(1) if data_emissao_match else "N/A"
        log(f"DEBUG: Data de Emissão extraída: {data_emissao}", "DEBUG")

        # Regex para extrair Prazo de Entrega
        prazo_entrega_match = re.search(r'PRAZO DE ENTREGA:\s*(\d{2}/\d{2}/\d{4})', text, re.IGNORECASE)
        prazo_entrega = prazo_entrega_match.group(1) if prazo_entrega_match else "N/A"
        log(f"DEBUG: Prazo de Entrega extraído: {prazo_entrega}", "DEBUG")

        # Regex para extrair Cidade de Destino (mais flexível)
        cidade_destino_match = re.search(r'CIDADE:\s*([A-Za-z\s\/]+?)(?:\n|DATA DE EMISSÃO:)', text, re.IGNORECASE | re.DOTALL)
        cidade_destino = cidade_destino_match.group(1).strip() if cidade_destino_match else "N/A"
        log(f"DEBUG: Cidade de Destino extraída: {cidade_destino}", "DEBUG")

        # --- REGEX PARA ITENS DE PRODUTO (Aplicado ao texto completo) ---
        item_pattern = re.compile(
            r'(\d+)\s+' # Quantidade (Grupo 1) - permite espaços e quebras de linha
            r'(?:CONJUNTO\s+ALUNO\s+TAMANHO\s+)?' # Texto opcional "CONJUNTO ALUNO TAMANHO "
            r'(CJA-\d{2})' # Modelo CJA (Grupo 2)
            r'.*?' # Qualquer coisa no meio (non-greedy)
            r'\(TAMPO\s+(MDF|PLASTICO|MASTICMOL)\)' # Tipo de Tampo (Grupo 3)
            , re.IGNORECASE | re.VERBOSE | re.DOTALL # re.DOTALL para que '.' inclua quebras de linha
        )
        
        # Iterar sobre todas as correspondências encontradas no texto completo
        for item_match in item_pattern.finditer(text):
            quantidade = int(item_match.group(1))
            modelo_cja = item_match.group(2).upper()
            tampo_tipo = item_match.group(3).upper()
            tipo_cja = "N/A" # Definido como N/A pois não está no padrão da linha do item neste PDF

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
            log(f"DEBUG: Item extraído: Quantidade={quantidade}, Modelo CJA={modelo_cja}, Tampo={tampo_tipo}", "DEBUG")
        
        log(f"DEBUG: Lista de itens extraídos antes do retorno: {extracted_items}", "DEBUG") 
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
            save_processed_emails(processed_emails) 
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
