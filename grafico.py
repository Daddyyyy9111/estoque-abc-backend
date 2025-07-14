from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
)
from reportlab.lib import colors
from reportlab.lib.units import cm
import matplotlib.pyplot as plt
import tempfile
import os
from datetime import datetime

def criar_grafico_barras(titulo, dados, cor="#4B8BBE"):
    fig, ax = plt.subplots(figsize=(6, 3.5))
    modelos = list(dados.keys())
    valores = list(dados.values())
    barras = ax.bar(modelos, valores, color=cor)
    
    ax.set_title(titulo, fontsize=14, weight='bold')
    ax.set_ylabel("Quantidade", fontsize=12)
    ax.grid(axis='y', linestyle='--', alpha=0.7)
    
    for barra in barras:
        altura = barra.get_height()
        ax.text(barra.get_x() + barra.get_width() / 2, altura + 0.5,
                f'{int(altura)}', ha='center', va='bottom', fontsize=10)
    
    plt.tight_layout()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
    plt.savefig(temp_file.name, dpi=150)
    plt.close()
    return temp_file.name

def calcular_qtd_producao(dados_estoque, dados_consumo):
    return {
        modelo: int(dados_estoque[modelo] / dados_consumo.get(modelo, 1))
        for modelo in dados_estoque
    }

def gerar_tabela_resumo(dados_producao, dados_estoque, dados_consumo, qtd_produzir):
    cabecalho = ["Modelo", "Produção", "Estoque", "Consumo (p/und)", "Produção Possível", "Status"]
    linhas = [cabecalho]

    for modelo in sorted(dados_producao.keys()):
        produzidos = dados_producao.get(modelo, 0)
        estoque = dados_estoque.get(modelo, 0)
        consumo = dados_consumo.get(modelo, 1)
        possivel = qtd_produzir.get(modelo, 0)

        status = "OK"
        if possivel < 20:
            status = "⚠️ Baixo"
        elif possivel > 100:
            status = "✅ Alto"

        linhas.append([
            modelo, produzidos, estoque, round(consumo, 2), possivel, status
        ])

    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 12),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
    ])
    
    tabela = Table(linhas, style=estilo, hAlign="CENTER")
    return tabela

def gerar_pdf_relatorio(titulo, dados_producao, dados_estoque, dados_consumo, arquivo_pdf):
    doc = SimpleDocTemplate(arquivo_pdf, pagesize=A4,
                            rightMargin=2 * cm, leftMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()

    estilo_titulo = ParagraphStyle(
        'Titulo',
        parent=styles['Heading1'],
        alignment=1,
        fontSize=20,
        spaceAfter=20,
        fontName='Helvetica-Bold'
    )
    estilo_normal = ParagraphStyle(
        'Normal',
        parent=styles['Normal'],
        fontSize=12,
        leading=18,
        spaceAfter=12,
    )
    estilo_kpi = ParagraphStyle(
        'KPI',
        parent=styles['Normal'],
        fontSize=14,
        textColor=colors.HexColor("#003366"),
        spaceAfter=10,
        leading=20
    )

    data_geracao = datetime.now().strftime('%d/%m/%Y %H:%M')

    elementos = [
        Paragraph(titulo, estilo_titulo),
        Paragraph(f"Data de geração do relatório: <b>{data_geracao}</b>", estilo_normal),
        Spacer(1, 12),
        Paragraph("<b>Sumário:</b><br/>"
                  "- Produção, Estoque e Possibilidade de Produção<br/>"
                  "- Tabelas e Gráficos<br/>"
                  "- Análise de Status e Planejamento<br/>", estilo_normal),
        PageBreak()
    ]

    qtd_produzir = calcular_qtd_producao(dados_estoque, dados_consumo)

    # Indicadores-Chave
    total_produzido = sum(dados_producao.values())
    total_estoque = sum(dados_estoque.values())
    total_possivel = sum(qtd_produzir.values())

    elementos += [
        Paragraph("<b>Indicadores Gerais:</b>", estilo_kpi),
        Paragraph(f"🔧 Total Produzido: <b>{total_produzido}</b>", estilo_normal),
        Paragraph(f"📦 Estoque Total: <b>{total_estoque}</b>", estilo_normal),
        Paragraph(f"🏭 Produção Possível Total: <b>{total_possivel}</b>", estilo_normal),
        Spacer(1, 12),
        Paragraph("<b>Resumo Tabelado:</b>", estilo_kpi),
        gerar_tabela_resumo(dados_producao, dados_estoque, dados_consumo, qtd_produzir),
        Spacer(1, 12)
    ]

    # Gráficos
    graficos_info = [
        ("Produção por Modelo", dados_producao, "#4B8BBE"),
        ("Estoque Atual por Modelo", dados_estoque, "#F08080"),
        ("Quantidade Possível de Produção", qtd_produzir, "#90EE90")
    ]

    arquivos_temp = []

    for titulo_grafico, dados, cor in graficos_info:
        caminho = criar_grafico_barras(titulo_grafico, dados, cor)
        elementos.append(Spacer(1, 12))
        elementos.append(Paragraph(f"<b>{titulo_grafico}</b>", estilo_normal))
        elementos.append(Image(caminho, width=16 * cm, height=9 * cm))
        arquivos_temp.append(caminho)

    elementos.append(PageBreak())

    # Comentários por modelo
    elementos.append(Paragraph("<b>Análise Individual por Modelo:</b>", estilo_kpi))
    for modelo in sorted(dados_producao.keys()):
        produzidos = dados_producao[modelo]
        estoque = dados_estoque[modelo]
        possivel = qtd_produzir[modelo]
        comentario = f"Modelo <b>{modelo}</b>: Produzido {produzidos}, Estoque {estoque}, pode produzir {possivel} unidades."

        if possivel < 20:
            comentario += " ⚠️ Estoque crítico, priorizar este modelo!"
        elif possivel > 100:
            comentario += " ✅ Estoque saudável."

        elementos.append(Paragraph(comentario, estilo_normal))

    elementos.append(Spacer(1, 24))

    # Dicas
    dicas = (
        "<b>Dicas para Planejamento:</b><br/>"
        "- 🔄 Atualize os dados regularmente para refletir a realidade.<br/>"
        "- 🟢 Priorize modelos com baixa produção possível.<br/>"
        "- 📉 Ajuste o planejamento conforme o consumo real médio.<br/>"
    )
    elementos.append(Paragraph(dicas, estilo_normal))

    doc.build(elementos)

    # Limpeza dos gráficos temporários
    for f in arquivos_temp:
        if os.path.exists(f):
            os.remove(f)

    print(f"PDF '{arquivo_pdf}' gerado com sucesso!")

if __name__ == "__main__":
    dados_producao_exemplo = {
        'CJA-03': 120,
        'CJA-04': 95,
        'CJA-05': 75,
        'CJA-06': 50,
    }
    dados_estoque_exemplo = {
        'CJA-03': 180,
        'CJA-04': 45,
        'CJA-05': 60,
        'CJA-06': 30,
    }
    dados_consumo_exemplo = {
        'CJA-03': 1.5,
        'CJA-04': 2,
        'CJA-05': 1,
        'CJA-06': 1.2,
    }

    gerar_pdf_relatorio(
        "Relatório Completo de Produção e Estoque",
        dados_producao_exemplo,
        dados_estoque_exemplo,
        dados_consumo_exemplo,
        "relatorio_completo.pdf"
    )