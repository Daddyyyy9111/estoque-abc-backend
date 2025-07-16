import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import credentials, firestore, auth
from functools import wraps
import pytz # Importa pytz para lidar com fusos horários

# Variável global para a instância do Firestore
db = None 

# Função para criar e configurar a aplicação Flask
def create_app():
    global db # Declara db como global para poder modificá-lo aqui
    app = Flask(__name__)
    
    # Configuração CORS: Aplicar CORS globalmente para todas as rotas e métodos
    # Isso deve garantir que o preflight OPTIONS seja tratado corretamente
    CORS(app, supports_credentials=True, resources={r"/*": {"origins": ["https://daddyyyy9111.github.io", "http://localhost:5000", "http://127.0.0.1:5000"], "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"]}})

    # Define o fuso horário para consistência (ajuste se necessário)
    TIMEZONE = 'America/Sao_Paulo'
    local_tz = pytz.timezone(TIMEZONE)

    try:
        firebase_config_str = os.environ.get('__firebase_config')
        if firebase_config_str:
            cred = credentials.Certificate(json.loads(firebase_config_str))
            # Verifica se o app já foi inicializado para evitar erro
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            db = firestore.client()
            print("Firebase Admin SDK initialized successfully.")
        else:
            print("Firebase config (__firebase_config) not found in environment variables. Running without Firestore persistence.")
    except ValueError as e:
        print(f"Error initializing Firebase Admin SDK: {e}")
        print("Ensure __firebase_config is correctly set and contains valid Firebase service account credentials.")
    except Exception as e:
        print(f"An unexpected error occurred during Firebase Admin SDK initialization: {e}")
        print("Please check the format of your __firebase_config environment variable.")

    # Decorator for authentication and role checking
    def token_required(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not db:
                return jsonify({"message": "Firestore não está configurado."}), 500

            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return jsonify({"message": "Token de autenticação ausente."}), 401

            try:
                id_token = auth_header.split(" ")[1]
                decoded_token = auth.verify_id_token(id_token)
                
                request.current_user_uid = decoded_token['uid']
                request.current_username = decoded_token.get('name', decoded_token.get('email', decoded_token['uid']))
                request.current_user_role = decoded_token.get('role', 'visualizador') # Default role

            except Exception as e:
                print(f"Erro de verificação de token: {e}")
                return jsonify({'message': 'Token inválido ou expirado!'}), 401
            return f(*args, **kwargs)
        return decorated

    # Rota de teste simples (SEM @token_required)
    @app.route('/test_route', methods=['GET', 'OPTIONS'])
    def test_route():
        return jsonify({"message": "Rota de teste funcionando!"}), 200

    # Endpoint to initialize/reset data (for testing purposes)
    @app.route('/initialize_data', methods=['POST'])
    def initialize_data():
        if db:
            try:
                # Clear existing stock data
                for doc_ref in db.collection('estoque').stream():
                    doc_ref.reference.delete()
                # Clear existing movements data
                for doc_ref in db.collection('movimentacoes').stream():
                    doc_ref.reference.delete()
                # Clear existing pending orders data
                for doc_ref in db.collection('pending_orders').stream():
                    doc_ref.reference.delete()
                
                # Clear existing users from Firestore and Firebase Auth
                users_to_delete = []
                for user in auth.list_users().users:
                    users_to_delete.append(user.uid)
                if users_to_delete:
                    auth.delete_users(users_to_delete) # Bulk delete users from Auth

                # Delete user documents from Firestore (using 'users_roles' now)
                for doc_ref in db.collection('users_roles').stream():
                    doc_ref.reference.delete()

                # Add default users to Firestore and Firebase Auth
                default_users = {
                    "carlos": {"password": "admin123", "role": "admin"},
                    "rose": {"password": "rose123", "role": "admin"},
                    "amanda": {"password": "amanda123", "role": "administrativo"},
                    "matheus": {"password": "matheus123", "role": "estoque_geral"},
                    "thiago": {"password": "producao123", "role": "producao"},
                    "rian": {"password": "rian123", "role": "visualizador"},
                    "automacao": {"password": "auto123", "role": "producao"} # NOVO USUÁRIO PARA AUTOMAÇÃO
                }
                for username, user_data in default_users.items():
                    email = f"{username}@example.com" # Firebase Auth requires an email
                    user_record = auth.create_user(
                        email=email,
                        password=user_data['password'],
                        display_name=username
                    )
                    auth.set_custom_user_claims(user_record.uid, {'role': user_data['role']})
                    # Store user details in 'users_roles' collection
                    db.collection('users_roles').document(user_record.uid).set({
                        'username': username,
                        'email': email,
                        'role': user_data['role']
                    })

                # Initial stock data (based on your provided spreadsheet image)
                initial_stock = [
                    {"modelo": "ASSENTO-ZURICH-CJA-06", "quantidade": 1597},
                    {"modelo": "ENCOSTO-ZURICH-CJA-06", "quantidade": 1620},
                    {"modelo": "ASSENTO-ZURICH-CJA-05", "quantidade": 150},
                    {"modelo": "ENCOSTO-ZURICH-CJA-05", "quantidade": 149},
                    {"modelo": "ASSENTO-ZURICH-CJA-04", "quantidade": 1170},
                    {"modelo": "ENCOSTO-ZURICH-CJA-04", "quantidade": 1170},
                    {"modelo": "ASSENTO-ZURICH-CJA-03", "quantidade": 554},
                    {"modelo": "ENCOSTO-ZURICH-CJA-03", "quantidade": 345},
                    
                    {"modelo": "ASSENTO-MASTICMOL-CJA-06", "quantidade": 0},
                    {"modelo": "ENCOSTO-MASTICMOL-CJA-06", "quantidade": 10},
                    {"modelo": "ASSENTO-MASTICMOL-CJA-05", "quantidade": 0},
                    {"modelo": "ENCOSTO-MASTICMOL-CJA-05", "quantidade": 0},
                    {"modelo": "ASSENTO-MASTICMOL-CJA-04", "quantidade": 10},
                    {"modelo": "ENCOSTO-MASTICMOL-CJA-04", "quantidade": 40},
                    {"modelo": "ASSENTO-MASTICMOL-CJA-03", "quantidade": 0},
                    {"modelo": "ENCOSTO-MASTICMOL-CJA-03", "quantidade": 0},

                    {"modelo": "PORTA-LIVRO", "quantidade": 6720},

                    {"modelo": "TAMPO-MDF-CJA-06", "quantidade": 552},
                    {"modelo": "TAMPO-PLASTICO-CJA-06", "quantidade": 1720},
                    {"modelo": "TAMPO-MASTICMOL-CJA-06", "quantidade": 0}, 
                    
                    {"modelo": "TAMPO-MDF-CJA-05", "quantidade": 200},
                    {"modelo": "TAMPO-PLASTICO-CJA-05", "quantidade": 730},
                    {"modelo": "TAMPO-MASTICMOL-CJA-05", "quantidade": 150},

                    {"modelo": "TAMPO-MDF-CJA-04", "quantidade": 93},
                    {"modelo": "TAMPO-PLASTICO-CJA-04", "quantidade": 530},
                    {"modelo": "TAMPO-MASTICMOL-CJA-04", "quantidade": 0},

                    {"modelo": "TAMPO-MDF-CJA-03", "quantidade": 216},
                    {"modelo": "TAMPO-PLASTICO-CJA-03", "quantidade": 1600},
                    {"modelo": "TAMPO-MASTICMOL-CJA-03", "quantidade": 0},

                    # Initial Conjuntos Prontos (Local)
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-ZURICH-CJA-06-MDF", "quantidade": 50},
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-ZURICH-CJA-06-PLASTICO", "quantidade": 100},
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-ZURICH-CJA-05-MDF", "quantidade": 20},
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-ZURICH-CJA-05-PLASTICO", "quantidade": 40},
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-MASTICMOL-CJA-06-MDF", "quantidade": 5},
                    {"modelo": "CONJUNTO-PRONTO-LOCAL-MASTICMOL-CJA-06-PLASTICO", "quantidade": 10},

                    # Initial Conjuntos Prontos (Distrito)
                    {"modelo": "CONJUNTO-PRONTO-DISTRITO-ZURICH-CJA-06-MDF", "quantidade": 10},
                    {"modelo": "CONJUNTO-PRONTO-DISTRITO-ZURICH-CJA-06-PLASTICO", "quantidade": 20},
                ]
                for item in initial_stock:
                    db.collection('estoque').add(item)

                return jsonify({"message": "Dados inicializados com sucesso no Firestore!"}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao inicializar dados no Firestore: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. A inicialização de dados persistentes não é possível."}), 500

    # Login endpoint (Frontend handles Firebase Auth login, this is just a placeholder/check)
    @app.route('/login', methods=['POST'])
    def login():
        data = request.get_json()
        username = data.get('username')
        
        if not username:
            return jsonify({"message": "Usuário é obrigatório."}), 400

        if db:
            try:
                # Frontend handles password verification via Firebase Auth client SDK
                # This endpoint only confirms user existence and returns role for session setup
                # We need to get the UID from the request.user (set by token_required or similar middleware)
                # If this endpoint is hit directly without a token, it will fail.
                # Assuming the frontend sends the token for this check.
                user_doc = db.collection('users_roles').document(request.current_user_uid).get()
                if user_doc.exists:
                    user_data = user_doc.to_dict()
                    return jsonify({"message": "Usuário encontrado!", "username": user_data.get('username'), "role": user_data.get('role', 'visualizador')}), 200
                else:
                    return jsonify({"message": "Usuário não encontrado no Firestore."}), 401
            except Exception as e:
                print(f"Erro no login com Firestore: {e}")
                return jsonify({"message": "Erro no servidor ao tentar login."}), 500
        else:
            return jsonify({"message": "Firestore não está configurado para login."}), 500


    # Logout endpoint (client-side token removal)
    @app.route('/logout', methods=['POST'])
    def logout():
        return jsonify({"message": "Logout bem-sucedido."}), 200

    # Endpoint to create a new user (admin only)
    @app.route('/create_user', methods=['POST'])
    @token_required
    def create_user():
        if request.current_user_role != 'admin':
            return jsonify({"message": "Acesso negado. Apenas administradores podem criar usuários."}), 403

        data = request.get_json()
        username = data.get('username')
        password = data.get('password')
        role = data.get('role')
        email = f"{username}@example.com" # Firebase Auth requires an email

        if not username or not password or not role:
            return jsonify({"message": "Usuário, senha e função são obrigatórios."}), 400
        
        allowed_roles = ['admin', 'producao', 'administrativo', 'visualizador', 'estoque_geral']
        if role not in allowed_roles:
            return jsonify({"message": f"Função inválida. Funções permitidas: {', '.join(allowed_roles)}."}), 400

        if db:
            try:
                # Create user in Firebase Authentication
                user_record = auth.create_user(
                    email=email,
                    password=password,
                    display_name=username
                )
                # Set custom claims for the user (role)
                auth.set_custom_user_claims(user_record.uid, {'role': role})

                # Store user details in 'users_roles' collection
                db.collection('users_roles').document(user_record.uid).set({
                    'username': username,
                    'email': email,
                    'role': role,
                    'uid': user_record.uid # Store UID as well
                })
                return jsonify({"message": f"Usuário '{username}' criado com sucesso!"}), 201
            except Exception as e:
                if "email-already-exists" in str(e):
                    return jsonify({"message": "Usuário com este nome já existe. Por favor, escolha outro."}), 409
                return jsonify({"message": f"Erro ao criar usuário: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. A criação de usuários persistentes não é possível."}), 500

    # Endpoint to get all users (admin only) - for display in frontend
    @app.route('/users', methods=['GET'])
    @token_required
    def get_users():
        if request.current_user_role != 'admin':
            return jsonify({"message": "Acesso negado. Apenas administradores podem visualizar usuários."}), 403
        
        if db:
            try:
                users_list = []
                # List all users from Firebase Auth
                for user in auth.list_users().users:
                    users_list.append({
                        "username": user.display_name,
                        "email": user.email,
                        "role": user.custom_claims.get('role', 'visualizador') if user.custom_claims else 'visualizador'
                    })
                return jsonify(users_list), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao buscar usuários do Firebase Auth: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível listar usuários."}), 500

    # Endpoint to delete a user (admin only)
    @app.route('/delete_user/<username>', methods=['DELETE'])
    @token_required
    def delete_user(username):
        if request.current_user_role != 'admin':
            return jsonify({"message": "Acesso negado. Apenas administradores podem deletar usuários."}), 403
        
        if request.current_username == username:
            return jsonify({"message": "Você não pode deletar seu próprio usuário."}), 400

        if db:
            try:
                user_to_delete_uid = None
                # Find user UID by username (display_name) or email
                for user in auth.list_users().users:
                    if user.display_name == username or user.email == f"{username}@example.com":
                        user_to_delete_uid = user.uid
                        break

                if user_to_delete_uid:
                    # Delete from Firebase Authentication
                    auth.delete_user(user_to_delete_uid)
                    # Delete from Firestore (if stored there)
                    db.collection('users_roles').document(user_to_delete_uid).delete() # Use UID as doc ID
                    return jsonify({"message": f"Usuário '{username}' deletado com sucesso!"}), 200
                else:
                    return jsonify({"message": "Usuário não encontrado."}), 404
            except Exception as e:
                return jsonify({"message": f"Erro ao deletar usuário: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível deletar usuários."}), 500

    # Endpoint to get stock data
    @app.route('/estoque', methods=['GET'])
    @token_required
    def get_estoque():
        if db:
            try:
                stock_items = []
                for doc in db.collection('estoque').stream():
                    item_data = doc.to_dict()
                    stock_items.append(item_data)
                return jsonify(stock_items), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao buscar estoque: {str(e)}"}), 500
        else:
            return jsonify([])

    # Endpoint to process manual entries (reajuste)
    @app.route('/reajuste_estoque', methods=['POST']) # Renomeado para refletir melhor a ação
    @token_required
    def reajuste_estoque(): # Renomeada a função
        if request.current_user_role not in ['producao', 'administrativo', 'admin', 'estoque_geral']:
            return jsonify({"message": "Acesso negado. Apenas usuários autorizados podem reajustar estoque."}), 403

        data = request.get_json()
        itens = data.get('itens', [])
        tipo_operacao = data.get('tipo_operacao') # 'adicionar' ou 'retirar'
        descricao = data.get('descricao', '')
        registrado_por = data.get('registrado_por') # Vem do frontend

        if not itens:
            return jsonify({"message": "Nenhum item para processar."}), 400

        if db:
            try:
                batch = db.batch()
                movimentacao_itens = []

                for item in itens:
                    componente = item.get('componente')
                    quantidade_movimentada = item.get('quantidade')

                    if not componente or quantidade_movimentada is None:
                        return jsonify({"message": "Item inválido: componente ou quantidade faltando."}), 400

                    # Determine the actual quantity to apply based on operation type
                    if tipo_operacao == 'retirar':
                        quantidade_movimentada = -quantidade_movimentada # Make it negative for subtraction

                    query = db.collection('estoque').where('modelo', '==', componente).limit(1)
                    docs = query.stream()
                    
                    found_doc_ref = None
                    found_doc_data = None
                    for doc in docs:
                        found_doc_ref = doc.reference
                        found_doc_data = doc.to_dict()
                        break
                    
                    if found_doc_ref:
                        # Check for sufficient stock if it's a withdrawal
                        if tipo_operacao == 'retirar' and found_doc_data['quantidade'] < abs(quantidade_movimentada):
                            return jsonify({"message": f"Estoque insuficiente para '{componente}'. Disponível: {found_doc_data['quantidade']}, Tentativa de retirada: {abs(quantidade_movimentada)}"}), 400
                        
                        batch.update(found_doc_ref, {'quantidade': firestore.Increment(quantidade_movimentada)})
                    else:
                        # If component not found, add it (only if quantity is positive for new entry)
                        if tipo_operacao == 'adicionar' and quantidade_movimentada > 0:
                            batch.set(db.collection('estoque').document(), {'modelo': componente, 'quantidade': quantidade_movimentada})
                        else:
                            return jsonify({"message": f"Erro: Componente '{componente}' não encontrado para retirada ou adição de quantidade zero/negativa."}), 404
                    
                    # Record the item as it was in the request (positive quantity for display)
                    movimentacao_itens.append({'componente': componente, 'quantidade': item.get('quantidade')})
                
                # Record the movement
                movement_record = {
                    "timestamp": datetime.now(local_tz),
                    "tipo": "Entrada - Manual" if tipo_operacao == 'adicionar' else "Saída - Manual", # Ajusta o tipo de movimento
                    "tipo_entrada": descricao, # Usando descrição como tipo_entrada para consistência com o frontend
                    "descricao": descricao,
                    "itens": movimentacao_itens,
                    "registrado_por": registrado_por
                }
                batch.set(db.collection('movimentacoes').document(), movement_record)

                batch.commit()
                return jsonify({"message": "Movimentação de estoque registrada com sucesso!"}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao processar reajuste de estoque: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível processar reajustes."}), 500

    # RENOMEADO: Endpoint para registrar saídas manuais (pedidos/OS)
    @app.route('/registrar_saida_manual', methods=['POST'])
    @token_required
    def registrar_saida_manual():
        if request.current_user_role not in ['producao', 'administrativo', 'admin', 'estoque_geral']:
            return jsonify({"message": "Acesso negado. Apenas usuários autorizados podem registrar saídas."}), 403

        data = request.get_json()
        os_number = data.get('os_number')
        cidade_destino = data.get('cidade_destino')
        data_emissao = data.get('data_emissao')
        prazo_entrega = data.get('prazo_entrega')
        itens = data.get('itens', []) # Itens são os modelos de conjuntos ou componentes avulsos
        registrado_por = data.get('registrado_por') # Vem do frontend

        if not all([os_number, cidade_destino, data_emissao, prazo_entrega]):
            return jsonify({"message": "Dados do pedido incompletos."}), 400
        if not itens:
            return jsonify({"message": "Nenhum item para processar no pedido manual."}), 400

        if db:
            try:
                batch = db.batch()
                movimentacao_itens_saida = []

                for item in itens:
                    # Determina o nome completo do modelo para busca no estoque
                    modelo_estoque = ""
                    if 'modelo_cja' in item and 'tampo_tipo' in item: # É um conjunto pronto
                        # Assumimos que saídas manuais de conjuntos prontos são sempre do estoque LOCAL
                        modelo_estoque = f"CONJUNTO-PRONTO-LOCAL-{item['tipo_cja'].upper()}-{item['modelo_cja'].upper()}-{item['tampo_tipo'].upper()}"
                    elif 'componente' in item: # É um componente avulso
                        modelo_estoque = item['componente']
                    else:
                        return jsonify({"message": "Item inválido no pedido manual: formato desconhecido."}), 400

                    quantidade_pedida = item.get('quantidade')

                    if not modelo_estoque or quantidade_pedida is None or quantidade_pedida <= 0:
                        return jsonify({"message": "Item inválido no pedido manual: modelo ou quantidade faltando/inválida."}), 400

                    query = db.collection('estoque').where('modelo', '==', modelo_estoque).limit(1)
                    docs = query.stream()
                    
                    found_doc = None
                    doc_ref = None
                    for doc in docs:
                        found_doc = doc.to_dict()
                        doc_ref = doc.reference
                        break

                    if found_doc:
                        if found_doc['quantidade'] < quantidade_pedida:
                            return jsonify({"message": f"Estoque insuficiente para '{modelo_estoque}'. Disponível: {found_doc['quantidade']}, Pedido: {quantidade_pedida}"}), 400
                        
                        batch.update(doc_ref, {'quantidade': firestore.Increment(-quantidade_pedida)})
                    else:
                        return jsonify({"message": f"Item '{modelo_estoque}' não encontrado no estoque."}), 404
                    
                    # Adiciona o item ao registro de movimentação com os detalhes originais
                    movimentacao_itens_saida.append(item)
                
                # Record the movement
                movement_record = {
                    "timestamp": datetime.now(local_tz),
                    "tipo": "Saída - Pedido",
                    "os_number": os_number,
                    "cidade_destino": cidade_destino,
                    "data_emissao": data_emissao,
                    "prazo_entrega": prazo_entrega,
                    "itens": movimentacao_itens_saida, # Store original items for detailed history
                    "registrado_por": registrado_por
                }
                batch.set(db.collection('movimentacoes').document(), movement_record)

                batch.commit()
                return jsonify({"message": "Pedido manual processado e estoque atualizado com sucesso!"}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao processar pedido manual: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível processar pedidos."}), 500

    # Endpoint to add finished sets (Conjuntos Prontos)
    @app.route('/add_conjuntos_prontos', methods=['POST'])
    @token_required
    def add_conjuntos_prontos():
        if request.current_user_role not in ['producao', 'administrativo', 'admin', 'estoque_geral']:
            return jsonify({"message": "Acesso negado. Apenas usuários de produção ou administrativo podem adicionar conjuntos prontos."}), 403

        data = request.get_json()
        tipo_cja = data.get('tipo_cja') # ZURICH, MASTICMOL
        modelo_cja = data.get('modelo_cja') # CJA-03, CJA-04, etc.
        tampo_tipo = data.get('tampo_tipo') # MDF, PLASTICO, MASTICMOL
        quantidade = data.get('quantidade')
        destino_estoque = data.get('destino_estoque') # 'local' ou 'distrito'
        registrado_por = data.get('registrado_por') # Vem do frontend

        if not all([tipo_cja, modelo_cja, tampo_tipo, quantidade, destino_estoque]):
            return jsonify({"message": "Dados incompletos para adicionar conjuntos prontos."}), 400
        if not isinstance(quantidade, int) or quantidade <= 0:
            return jsonify({"message": "Quantidade deve ser maior que zero."}), 400
        if destino_estoque not in ['local', 'distrito']:
            return jsonify({"message": "Destino de estoque inválido. Use 'local' ou 'distrito'."}), 400

        finished_set_model_name = f"CONJUNTO-PRONTO-{destino_estoque.upper()}-{tipo_cja.upper()}-{modelo_cja.upper()}-{tampo_tipo.upper()}"

        if db:
            try:
                batch = db.batch()

                query = db.collection('estoque').where('modelo', '==', finished_set_model_name).limit(1)
                docs = query.stream()
                
                found_doc_ref = None
                for doc in docs:
                    found_doc_ref = doc.reference
                    break

                if found_doc_ref:
                    batch.update(found_doc_ref, {'quantidade': firestore.Increment(quantidade)})
                else:
                    batch.set(db.collection('estoque').document(), {'modelo': finished_set_model_name, 'quantidade': quantidade})

                # Record the movement
                movement_record = {
                    "timestamp": datetime.now(local_tz),
                    "tipo": "Produção - Conjunto Pronto",
                    "tipo_cja": tipo_cja,
                    "modelo_cja": modelo_cja,
                    "tampo_tipo": tampo_tipo,
                    "quantidade": quantidade,
                    "destino_estoque": destino_estoque,
                    "registrado_por": registrado_por
                }
                batch.set(db.collection('movimentacoes').document(), movement_record)

                batch.commit()
                return jsonify({"message": f"{quantidade} conjuntos '{finished_set_model_name}' adicionados ao estoque {destino_estoque}."}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao adicionar conjuntos prontos: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível adicionar conjuntos prontos."}), 500

    # Endpoint to get movements data
    @app.route('/movimentacoes', methods=['GET'])
    @token_required
    def get_movimentacoes():
        if db:
            try:
                movements = []
                for doc in db.collection('movimentacoes').stream():
                    movements.append(doc.to_dict())
                # Sort by timestamp in descending order (most recent first)
                movements.sort(key=lambda x: x.get('timestamp', datetime.min).isoformat(), reverse=True)
                return jsonify(movements), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao buscar movimentações: {str(e)}"}), 500
        else:
            return jsonify([])

    # Rotas para Pedidos Pendentes (SEM @token_required)
    @app.route('/pedidos_pendentes', methods=['GET', 'OPTIONS'])
    def get_pedidos_pendentes():
        # Removido a verificação de role para debug de 404/CORS
        # if request.current_user_role not in ['producao', 'administrativo', 'admin', 'estoque_geral', 'visualizador']:
        #     return jsonify({"message": "Permissão negada"}), 403

        if db:
            try:
                orders_ref = db.collection('pending_orders')
                # Você pode adicionar filtros aqui se quiser, ex: .where('status', '!=', 'Feito')
                docs = orders_ref.stream()
                
                pending_orders = []
                for doc in docs:
                    order_data = doc.to_dict()
                    order_data['id'] = doc.id # Adiciona o ID do documento para uso no frontend
                    # Converte timestamps para string ISO se existirem
                    if 'created_at' in order_data and isinstance(order_data['created_at'], datetime):
                        order_data['created_at'] = order_data['created_at'].isoformat()
                    if 'updated_at' in order_data and isinstance(order_data['updated_at'], datetime):
                        order_data['updated_at'] = order_data['updated_at'].isoformat()
                    pending_orders.append(order_data)
                
                # Opcional: ordenar pedidos pendentes por data de criação ou OS
                pending_orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)

                return jsonify(pending_orders), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao buscar pedidos pendentes: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível buscar pedidos pendentes."}), 500

    @app.route('/pedidos_pendentes', methods=['POST', 'OPTIONS'])
    def create_pedidos_pendentes():
        # Removido a verificação de role para debug de 404/CORS
        # if request.current_user_role not in ['producao', 'administrativo', 'admin', 'estoque_geral', 'visualizador']:
        #     pass 

        data = request.get_json()
        os_number = data.get('os_number')
        cidade_destino = data.get('cidade_destino')
        itens = data.get('itens')
        # O 'registrado_por' pode vir do script de automação como 'Sistema' ou do usuário logado
        registrado_por = data.get('registrado_por', 'Sistema de Automação' if not request.current_username else request.current_username) 

        if not all([os_number, cidade_destino, itens]):
            return jsonify({"message": "Dados do pedido incompletos"}), 400
        if not isinstance(itens, list) or not itens:
            return jsonify({"message": "Itens do pedido devem ser uma lista não vazia"}), 400

        for item in itens:
            # Itens devem ser conjuntos CJA com tipo_cja, modelo_cja, tampo_tipo e quantidade
            if not all([item.get('tipo_cja'), item.get('modelo_cja'), item.get('tampo_tipo'), item.get('quantidade')]):
                return jsonify({"message": "Detalhes de item incompletos no pedido (tipo_cja, modelo_cja, tampo_tipo, quantidade são obrigatórios)"}), 400
            if not isinstance(item.get('quantidade'), int) or item.get('quantidade') <= 0:
                return jsonify({"message": "Quantidade de item inválida (deve ser um número inteiro positivo)"}), 400

        if db:
            try:
                order_data = {
                    "os_number": os_number,
                    "cidade_destino": cidade_destino,
                    "itens": itens,
                    "status": "Pendente", # Sempre começa como Pendente
                    "created_at": datetime.now(local_tz),
                    "created_by": registrado_por,
                    "updated_at": datetime.now(local_tz),
                    "updated_by": registrado_por
                }

                doc_ref = db.collection('pending_orders').add(order_data)
                return jsonify({"message": "Pedido pendente criado com sucesso!", "id": doc_ref[1].id}), 201
            except Exception as e:
                return jsonify({"message": f"Erro ao criar pedido pendente: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível criar pedidos pendentes."}), 500

    @app.route('/pedidos_pendentes/<order_id>', methods=['PUT', 'OPTIONS'])
    @token_required # Mantido para PUT, pois é uma ação que modifica dados
    def update_pedidos_pendentes_status(order_id):
        if request.current_user_role not in ['producao', 'admin']: # Apenas produção e admin podem mudar status
            return jsonify({"message": "Permissão negada para alterar status do pedido"}), 403

        data = request.get_json()
        new_status = data.get('status')
        updated_by = data.get('updated_by') # Vem do frontend

        if not new_status:
            return jsonify({"message": "Status é obrigatório"}), 400

        if db:
            try:
                order_ref = db.collection('pending_orders').document(order_id)
                order_doc = order_ref.get()

                if not order_doc.exists:
                    return jsonify({"message": "Pedido não encontrado"}), 404

                current_order_data = order_doc.to_dict()
                current_status = current_order_data.get('status')

                # REMOVIDO: Lógica de desconto de estoque e registro de movimentação
                # Esta seção foi removida para garantir que a atualização de status de pedido pendente
                # NÃO DEDUZ O ESTOQUE AUTOMATICAMENTE, conforme sua clarificação.
                # O estoque só será afetado por "Registrar Saída Manual" ou "Reajuste de Estoque".
                
                # Atualiza o status do pedido pendente
                order_ref.update({
                    'status': new_status,
                    'updated_at': datetime.now(local_tz),
                    'updated_by': updated_by
                })
                return jsonify({"message": f"Status do pedido {order_id} atualizado para {new_status}"}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao atualizar status do pedido: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível atualizar pedidos pendentes."}), 500

    @app.route('/pedidos_pendentes/<order_id>', methods=['DELETE', 'OPTIONS'])
    @token_required # Mantido para DELETE, pois é uma ação que modifica dados
    def delete_pedidos_pendentes(order_id):
        if request.current_user_role not in ['admin']: # Apenas admin pode deletar pedidos pendentes
            return jsonify({"message": "Permissão negada para deletar pedido pendente"}), 403

        if db:
            try:
                order_ref = db.collection('pending_orders').document(order_id)
                order_doc = order_ref.get()

                if not order_doc.exists:
                    return jsonify({"message": "Pedido pendente não encontrado"}), 404
                
                order_ref.delete()
                return jsonify({"message": f"Pedido pendente {order_id} deletado com sucesso!"}), 200
            except Exception as e:
                return jsonify({"message": f"Erro ao deletar pedido pendente: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível deletar pedidos pendentes."}), 500


    # Rota para Produção por CJA (para o Dashboard) - Agora aceita filtros e retorna dados por data
    @app.route('/production_summary', methods=['GET'])
    @token_required
    def get_production_summary():
        if request.current_user_role not in ['producao', 'admin', 'estoque_geral', 'visualizador']:
            return jsonify({"message": "Permissão negada"}), 403

        period = request.args.get('period', 'weekly') # 'weekly' or 'monthly'
        cja_model_filter = request.args.get('cja_model') # Ex: CJA-06
        tampo_type_filter = request.args.get('tampo_type') # Ex: MDF, PLASTICO

        if db:
            try:
                today = datetime.now(local_tz)
                if period == 'weekly':
                    # Começa no início do dia 7 dias atrás
                    start_date = today - timedelta(days=7)
                    start_date = datetime(start_date.year, start_date.month, start_date.day, 0, 0, 0, tzinfo=local_tz)
                else: # monthly
                    # Começa no início do mês atual (para 6 meses, a lógica de agregação será no frontend)
                    start_date = datetime(today.year, today.month - 5, 1, 0, 0, 0, tzinfo=local_tz) # Busca 6 meses para trás

                production_summary = {} # Dicionário para armazenar produção por período (data)

                movimentacoes_ref = db.collection('movimentacoes')
                query = movimentacoes_ref.where('tipo', '==', 'Produção - Conjunto Pronto').where('timestamp', '>=', start_date)
                
                if cja_model_filter:
                    query = query.where('modelo_cja', '==', cja_model_filter)
                if tampo_type_filter:
                    query = query.where('tampo_tipo', '==', tampo_type_filter)

                docs = query.stream()
                for doc in docs:
                    mov = doc.to_dict()
                    quantity = mov.get('quantidade', 0)
                    
                    # Formata a chave do dicionário com base no período
                    if period == 'weekly':
                        # Formato: DD/MM (ex: 14/Jul)
                        date_key = mov['timestamp'].strftime('%d/%b') 
                    else: # monthly
                        # Formato: MMM/YY (ex: Jul/25)
                        date_key = mov['timestamp'].strftime('%b/%y')
                    
                    production_summary[date_key] = production_summary.get(date_key, 0) + quantity
                
                # Garante que as chaves estejam ordenadas cronologicamente
                # Usar um ano fixo para comparação para evitar problemas de ano na ordenação de meses/dias
                def sort_key_func(x):
                    if period == 'weekly':
                        # Adiciona um ano fixo para que a comparação de data funcione corretamente
                        # Assume que a semana é do ano atual para ordenação
                        current_year = datetime.now(local_tz).year
                        return datetime.strptime(x + f'/{current_year}', '%d/%b/%Y')
                    else: # monthly
                        # Assume que o ano está no formato 'YY' e o completa para 'YYYY'
                        return datetime.strptime(x, '%b/%y')

                sorted_keys = sorted(production_summary.keys(), key=sort_key_func)
                
                # Cria um dicionário ordenado para a resposta
                ordered_production_summary = {k: production_summary[k] for k in sorted_keys}

                return jsonify(ordered_production_summary), 200
            except Exception as e:
                print(f"Erro no production_summary: {e}") # Adiciona log de erro
                return jsonify({"message": f"Erro ao buscar resumo de produção: {str(e)}"}), 500
        else:
            return jsonify({"message": "Firestore não está configurado. Não é possível buscar resumo de produção."}), 500
    
    # Retorna a instância do aplicativo Flask
    return app

# Esta é a parte que o Gunicorn vai chamar
app = create_app()

if __name__ == '__main__':
    # Quando rodando localmente, use app.run()
    app.run(debug=True, host='0.0.0.0', port=os.environ.get('PORT', 5000))
