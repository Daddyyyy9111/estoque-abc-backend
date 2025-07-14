// URL base da sua API Flask no Render.com
const API_BASE_URL = 'https://estoque-abc-frontend.onrender.com';

// Função para buscar dados de estoque da API
async function fetchEstoqueData() {
    try {
        const response = await fetch(`${API_BASE_URL}/estoque`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Dados de estoque recebidos:', data);
        return data;
    } catch (error) {
        console.error('Erro ao buscar dados de estoque:', error);
        return []; // Retorna um array vazio em caso de erro
    }
}

// Função para renderizar os dados nas tabelas
function renderEstoqueTables(estoqueData) {
    console.log('renderEstoqueTables: Dados para renderizar:', estoqueData);

    // Limpa as tabelas existentes e as mensagens de "nenhum dado"
    document.querySelectorAll('table tbody').forEach(tbody => tbody.innerHTML = '');
    document.querySelectorAll('.no-data').forEach(p => p.style.display = 'block'); // Mostra todas por padrão

    const tables = {
        'ZURICH': document.querySelector('#table-zurich tbody'),
        'MASTICMOL': document.querySelector('#table-masticmol tbody'),
        'TAMPOS': document.querySelector('#table-tampos tbody')
    };

    const noDataMessages = {
        'ZURICH': document.querySelector('#no-data-zurich'),
        'MASTICMOL': document.querySelector('#no-data-masticmol'),
        'TAMPOS': document.querySelector('#no-data-tampos')
    };

    let hasZurichData = false;
    let hasMasticmolData = false;
    let hasTamposData = false;

    estoqueData.forEach(item => {
        console.log('Processando item:', item);
        const row = document.createElement('tr');

        // Lógica para TAMPOS (com base nos dados de teste que você tem)
        if (item.tampo) {
            row.innerHTML = `
                <td>${item.modelo}</td>
                <td>${item.quantidade}</td>
                <td>${item.tampo}</td>
            `;
            tables['TAMPOS'].appendChild(row);
            hasTamposData = true;
        }
        // Se você tiver dados para Zurich/Masticmol no futuro, adicione a lógica aqui.
        // Exemplo:
        // if (item.modelo.includes('ZURICH')) {
        //     row.innerHTML = `<td>${item.modelo}</td><td>${item.assento_zurich}</td><td>${item.encosto_zurich}</td>`;
        //     tables['ZURICH'].appendChild(row);
        //     hasZurichData = true;
        // }
    });

    // Oculta as mensagens de "nenhum dado" se houver dados
    if (hasZurichData) noDataMessages['ZURICH'].style.display = 'none';
    if (hasMasticmolData) noDataMessages['MASTICMOL'].style.display = 'none';
    if (hasTamposData) noDataMessages['TAMPOS'].style.display = 'none';

    // Garante que se não houver dados, a mensagem de "nenhum dado" apareça para aquela tabela
    if (!hasZurichData) noDataMessages['ZURICH'].style.display = 'block';
    if (!hasMasticmolData) noDataMessages['MASTICMOL'].style.display = 'block';
    if (!hasTamposData) noDataMessages['TAMPOS'].style.display = 'block';

    console.log('renderEstoqueTables: Processamento concluído.');
}

// Função para buscar e renderizar dados de movimentações (exemplo)
async function fetchAndRenderMovimentacoes() {
    try {
        const response = await fetch(`${API_BASE_URL}/movimentacoes`);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        const data = await response.json();
        console.log('Dados de movimentações recebidos:', data);
        // Lógica para renderizar movimentações aqui
    } catch (error) {
        console.error('Erro ao buscar dados de movimentações:', error);
    }
}

// Função principal para carregar os dados ao carregar a página
async function showSection(sectionId) {
    if (sectionId === 'estoque') {
        const estoqueData = await fetchEstoqueData();
        renderEstoqueTables(estoqueData);
    } else if (sectionId === 'movimentacoes') {
        await fetchAndRenderMovimentacoes();
    }
}

// Carrega a seção de estoque ao carregar a página
document.addEventListener('DOMContentLoaded', () => {
    showSection('estoque');
});
