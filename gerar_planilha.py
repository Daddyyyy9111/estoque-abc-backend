import pandas as pd
from datetime import datetime, timedelta

# Criar dados fictícios para produção
datas = [datetime.now() - timedelta(days=i) for i in range(7)]  # últimos 7 dias
modelos = ['CJA-03', 'CJA-04']
dados = []

for i, data in enumerate(datas):
    for modelo in modelos:
        quantidade = max(0, int(10 + (5 - i) + (hash(modelo) % 5)))  # número aleatório simples
        dados.append({
            'DATA': data.strftime('%Y-%m-%d'),
            'MODELO': modelo,
            'QUANTIDADE': quantidade
        })

# Criar DataFrame
df = pd.DataFrame(dados)

# Salvar em Excel
df.to_excel('producao.xlsx', index=False)

print("Planilha 'producao.xlsx' criada com dados de teste.")
