from flask import Flask, jsonify, request
import db_manager # Importa o módulo de gerenciamento de banco de dados
from datetime import datetime

app = Flask(__name__)

# Configurações para permitir requisições de origens diferentes (CORS)
# Isso é importante porque sua página HTML será servida de um local (seu navegador)
# e a API de outro (o servidor Flask). Para produção, configure CORS de forma mais restrita.
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*') # Permite qualquer origem
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

@app.route('/')
def home():
    """Página inicial da API."""
    return "API do Sistema de Estoque ABC Móveis está funcionando!"

@app.route('/api/estoque', methods=['GET'])
def get_estoque():
    """
    Endpoint para obter todos os dados do estoque atual.
    Retorna uma lista de objetos JSON.
    """
    estoque_data = db_manager.get_estoque_data()
    return jsonify(estoque_data)

@app.route('/api/movimentacoes', methods=['GET'])
def get_movimentacoes():
    """
    Endpoint para obter todos os dados das movimentações.
    Retorna uma lista de objetos JSON.
    """
    movimentacoes_data = db_manager.get_movimentacoes_data()
    return jsonify(movimentacoes_data)

# Você pode adicionar mais endpoints aqui para:
# - Inserir novas movimentações manualmente
# - Atualizar estoque manualmente
# - Buscar estoque por componente/modelo específico
# - etc.

if __name__ == '__main__':
    # Para rodar a API, use: python app.py
    # Ela estará disponível em http://127.0.0.1:5000/
    # O debug=True permite recarregamento automático e mensagens de erro detalhadas.
    app.run(debug=True,  host='0.0.0.0')
