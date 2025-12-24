@echo off
echo Instalando dependencias do Python...
pip install -r requirements.txt
echo.
echo Instalando navegadores do Playwright...
playwright install chromium
echo.
echo Tudo pronto! Agora voce pode rodar o iniciar_sistema.bat
pause
