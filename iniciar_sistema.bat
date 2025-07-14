@echo off
title Iniciar Sistema de Estoque ABC

:: Define o caminho para a pasta do seu projeto
set "PROJECT_DIR=C:\Users\Carlao\Desktop\estoque"

:: Define o caminho para o executável do ngrok
:: Assumindo que ngrok.exe está dentro da pasta do projeto agora.
:: SE O NGROK.EXE ESTIVER EM OUTRO LUGAR, AJUSTE ESTA LINHA:
:: Exemplo: set "NGROK_EXE=C:\Users\SeuUsuario\Downloads\ngrok.exe"
set "NGROK_EXE=%PROJECT_DIR%\ngrok.exe"

echo.
echo =========================================
echo  Iniciando Sistema de Estoque ABC Movel
echo =========================================
echo.

:: --- Iniciar o Servidor Flask (backend_app.py) ---
echo Iniciando o servidor Flask (backend_app.py)...
start "Flask Server" cmd /k "cd /d "%PROJECT_DIR%" && call .\venv\Scripts\activate && python backend_app.py"

:: --- Iniciar o Processador de E-mails (automacao.py) ---
echo Iniciando o processador de e-mails (automacao.py)...
start "Email Processor" cmd /k "cd /d "%PROJECT_DIR%" && call .\venv\Scripts\activate && python automacao.py"

:: --- Iniciar o ngrok ---
echo Iniciando o ngrok...
echo.
echo =========================================================================
echo === ATENCAO: COPIE A URL HTTPS DO NGROK QUE APARECERA NA NOVA JANELA! ===
echo =========================================================================
echo.
start "ngrok Tunnel" cmd /k "cd /d "%PROJECT_DIR%" && "%NGROK_EXE%" http 5000"

echo.
echo Todos os componentes foram iniciados em novas janelas.
echo Mantenha estas janelas abertas para o sistema funcionar.
echo.
echo =========================================================================
echo === PROXIMOS PASSOS OBRIGATORIOS (MANUAIS) PARA ACESSO EXTERNO: ===
echo =========================================================================
echo 1. Na janela do 'ngrok Tunnel', COPIE a URL HTTPS (ex: https://XXXXX.ngrok-free.app).
echo 2. Abra o arquivo 'estoque.html' (ou 'index.html') na pasta '%PROJECT_DIR%' no seu editor (VS Code).
echo 3. SUBSTITUA a URL antiga em 'const API_BASE_URL = ...;' pela NOVA URL do ngrok.
echo    (Certifique-se de que nao ha espacos antes do 'https://'!)
echo 4. SALVE o arquivo HTML.
echo 5. No terminal, na pasta '%PROJECT_DIR%', execute os comandos Git:
echo    git add .
echo    git commit -m "Atualiza URL do ngrok"
echo    git push -u origin main
echo 6. Aguarde o GitHub Pages atualizar (1-5 minutos).
echo 7. Compartilhe o link do seu GitHub Pages (https://daddyyyy9111.github.io/estoque-abc-frontend/estoque.html) com seus colegas.
echo =========================================================================
echo.
pause
