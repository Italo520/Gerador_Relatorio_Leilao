import flet as ft
import json
import os
import subprocess
import re
import threading
from datetime import datetime
import shutil
from playwright.sync_api import sync_playwright

# Configurações
ARQUIVO_JSON = 'leiloes_completo.json'
ARQUIVO_TEMPLATE = 'Relatório Leilões.html'
ARQUIVO_SCRAPER = 'scraper.py'

class SistemaLeiloes:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_page()
        
        self.leiloes_data = []
        self.leiloes_online = []
        self.selected_leilao = None
        self.scraper_running = False
        
        self.build_ui()
        
        # File Picker para salvar PDF
        self.file_picker = ft.FilePicker(on_result=self.concluir_geracao_pdf)
        self.page.overlay.append(self.file_picker)
        
        self.carregar_dados()

    def setup_page(self):
        self.page.title = "Gerador de Relatórios de Leilão"
        self.page.theme_mode = ft.ThemeMode.LIGHT
        self.page.padding = 20
        self.page.window_width = 1280
        self.page.window_height = 800
        self.page.bgcolor = "#f5f5f5"

    def build_ui(self):
        # Header
        self.header = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.GAVEL, size=30, color=ft.Colors.BLUE_600),
                    ft.Text("Gerador de Relatórios de Leilão", size=24, weight=ft.FontWeight.BOLD, color=ft.Colors.BLUE_800),
                ],
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=ft.padding.only(bottom=20)
        )

        # Sidebar (Controles e Lista de Leilões)
        # Importar por URL
        self.input_url = ft.TextField(
            hint_text="Cole a URL do leilão aqui...",
            text_size=12,
            height=40,
            content_padding=10,
            expand=True
        )
        self.btn_importar = ft.IconButton(
            icon=ft.Icons.DOWNLOAD,
            icon_color=ft.Colors.BLUE_600,
            tooltip="Baixar leilão desta URL",
            on_click=self.importar_leilao_url
        )

        # Filtro
        self.input_filtro = ft.TextField(
            hint_text="Filtrar lista...",
            prefix_icon=ft.Icons.FILTER_LIST,
            text_size=12,
            height=40,
            content_padding=10,
            on_change=self.filtrar_lista
        )
        
        self.status_text = ft.Text("Pronto", size=12, color=ft.Colors.GREY_600)
        self.progress_bar = ft.ProgressBar(width=None, visible=False)

        self.lista_leiloes = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
        )

        self.sidebar = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Importar Leilão", weight=ft.FontWeight.BOLD),
                    ft.Row([self.input_url, self.btn_importar], spacing=5),
                    
                    self.progress_bar,
                    self.status_text,
                    
                    ft.Divider(height=10),
                    ft.Text("Leilões Baixados", weight=ft.FontWeight.BOLD),
                    self.input_filtro,
                    self.lista_leiloes,
                ],
                spacing=10,
            ),
            width=300,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_300),
        )

        # Área Principal (Detalhes e Preview)
        self.content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)
        
        self.main_container = ft.Container(
            content=self.content_area,
            expand=True,
            bgcolor=ft.Colors.WHITE,
            border_radius=10,
            padding=20,
            border=ft.border.all(1, ft.Colors.GREY_300),
            margin=ft.margin.only(left=10)
        )

        # Layout Principal
        self.page.add(
            self.header,
            ft.Row(
                [self.sidebar, self.main_container],
                expand=True,
                vertical_alignment=ft.CrossAxisAlignment.START
            )
        )

    def carregar_dados(self):
        # Carregar dados locais
        if os.path.exists(ARQUIVO_JSON):
            try:
                with open(ARQUIVO_JSON, 'r', encoding='utf-8') as f:
                    self.leiloes_data = json.load(f)
            except Exception as e:
                self.mostrar_mensagem(f"Erro ao ler dados locais: {e}", erro=True)
                self.leiloes_data = []
        else:
            self.leiloes_data = []

        self.atualizar_lista_leiloes()

    def atualizar_lista_leiloes(self):
        self.lista_leiloes.controls.clear()
        
        # Mapear dados locais por URL
        local_map = {l.get('leilao_url'): l for l in self.leiloes_data if l.get('leilao_url')}
        
        # Apenas URLs locais
        todos_urls = set(local_map.keys())
        
        if not todos_urls:
            self.lista_leiloes.controls.append(ft.Text("Nenhum leilão baixado."))
            self.page.update()
            return

        lista_ordenada = sorted(list(todos_urls))
        termo_filtro = self.input_filtro.value.lower() if self.input_filtro.value else ""

        count_exibidos = 0
        for url in lista_ordenada:
            local_info = local_map.get(url)
            
            titulo = local_info['leilao_titulo']
            
            # Aplicar filtro
            if termo_filtro and termo_filtro not in titulo.lower():
                continue
                
            count_exibidos += 1
            lotes_count = local_info['total_lotes']
            
            # Icone de status (sempre baixado aqui)
            icon = ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN, size=20)
            sub_text = f"{lotes_count} lotes baixados"
            bg_color = ft.Colors.BLUE_50 if self.selected_leilao == local_info else ft.Colors.WHITE
            border_color = ft.Colors.BLUE_200 if self.selected_leilao == local_info else ft.Colors.GREY_300

            # Botão de Ação (Baixar/Atualizar)
            btn_baixar = ft.IconButton(
                icon=ft.Icons.REFRESH,
                icon_color=ft.Colors.BLUE_600,
                tooltip="Atualizar este leilão",
                on_click=lambda e, u=url: self.baixar_leilao(u)
            )

            card_content = ft.Row([
                icon,
                ft.Column([
                    ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13, width=160, no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(sub_text, size=11, color=ft.Colors.GREY_600)
                ], expand=True, spacing=2),
                btn_baixar
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

            card = ft.Container(
                content=card_content,
                padding=10,
                border_radius=5,
                bgcolor=bg_color,
                border=ft.border.all(1, border_color),
                on_click=lambda e, l=local_info: self.selecionar_leilao(l) if l else None,
                ink=True,
            )
            self.lista_leiloes.controls.append(card)
            
        if count_exibidos == 0 and termo_filtro:
             self.lista_leiloes.controls.append(ft.Text("Nenhum leilão corresponde ao filtro.", size=12, italic=True))
        
        self.page.update()

    def filtrar_lista(self, e):
        self.atualizar_lista_leiloes()

    def selecionar_leilao(self, leilao):
        self.selected_leilao = leilao
        self.atualizar_lista_leiloes() # Para atualizar o destaque
        self.mostrar_detalhes_leilao()

    def mostrar_detalhes_leilao(self):
        self.content_area.controls.clear()
        
        if not self.selected_leilao:
            self.content_area.controls.append(ft.Text("Selecione um leilão para ver os detalhes."))
            self.page.update()
            return

        lotes = self.selected_leilao.get('lotes', [])
        titulo = self.selected_leilao.get('leilao_titulo', 'Leilão')
        
        # Header dos Detalhes
        header_detalhes = ft.Row(
            [
                ft.Column([
                    ft.Text(titulo, size=20, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Total de Lotes: {len(lotes)}", color=ft.Colors.GREY_700),
                ], expand=True),
                ft.ElevatedButton(
                    "Gerar Relatório HTML",
                    icon=ft.Icons.DESCRIPTION,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_600, color=ft.Colors.WHITE),
                    on_click=self.gerar_relatorio_html
                ),
                ft.ElevatedButton(
                    "Gerar PDF",
                    icon=ft.Icons.PICTURE_AS_PDF,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.RED_600, color=ft.Colors.WHITE),
                    on_click=self.iniciar_geracao_pdf
                )
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN
        )
        
        # Tabela de Preview
        tabela = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Lote")),
                ft.DataColumn(ft.Text("Título/Descrição")),
                ft.DataColumn(ft.Text("Valor")),
                ft.DataColumn(ft.Text("Link")),
            ],
            rows=[],
            border=ft.border.all(1, ft.Colors.GREY_200),
            vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_200),
            horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_200),
        )

        for lote in lotes[:50]: # Mostrar apenas os primeiros 50 para performance no preview
            titulo_lote = self.limpar_titulo(lote, titulo)
            valor = lote.get('valor_leilao', '') or lote.get('valor_minimo', '')
            
            tabela.rows.append(
                ft.DataRow(
                    cells=[
                        ft.DataCell(ft.Text(lote.get('numero_lote', '').replace('LOTE ', ''))),
                        ft.DataCell(ft.Column([
                            ft.Text(titulo_lote, weight=ft.FontWeight.BOLD, size=12),
                            ft.Text(lote.get('descricao', '')[:50] + "...", size=10, color=ft.Colors.GREY_600)
                        ], spacing=2)),
                        ft.DataCell(ft.Text(valor)),
                        ft.DataCell(ft.IconButton(
                            icon=ft.Icons.LINK, 
                            url=lote.get('url'), 
                            tooltip="Abrir no navegador"
                        )),
                    ]
                )
            )

        if len(lotes) > 50:
            aviso = ft.Text(f"... e mais {len(lotes) - 50} lotes.", italic=True, color=ft.Colors.GREY_500)
        else:
            aviso = ft.Container()

        self.content_area.controls.extend([
            header_detalhes,
            ft.Divider(),
            ft.Text("Pré-visualização (Primeiros 50 lotes):", weight=ft.FontWeight.BOLD),
            ft.Column([tabela, aviso], scroll=ft.ScrollMode.AUTO, expand=True)
        ])
        
        self.page.update()

    def limpar_titulo(self, lote, titulo_leilao):
        """Melhora o título do lote se ele for igual ao do leilão"""
        titulo = lote.get('titulo', '')
        # Se o título do lote for genérico ou igual ao do leilão, tenta extrair da URL ou descrição
        if not titulo or titulo == titulo_leilao or titulo == "Título não encontrado" or titulo == "LOTE":
            # Tenta extrair da descrição (segunda linha geralmente é o veículo)
            descricao = lote.get('descricao', '')
            if descricao:
                linhas = descricao.split('\n')
                if len(linhas) > 1:
                    candidato = linhas[1].strip()
                    if candidato:
                        return candidato
            
            # Fallback para URL
            url = lote.get('url', '')
            if url:
                try:
                    # Pega a última parte da URL (slug)
                    slug = url.rstrip('/').split('/')[-1]
                    # Remove números iniciais se houver e formata
                    slug_limpo = slug.replace('-', ' ').upper()
                    return slug_limpo
                except:
                    pass
        return titulo

    def _gerar_conteudo_html(self):
        if not self.selected_leilao:
            return None, None

        if not os.path.exists(ARQUIVO_TEMPLATE):
            self.mostrar_mensagem(f"Template '{ARQUIVO_TEMPLATE}' não encontrado!", erro=True)
            return None, None

        try:
            # Preparar dados para o HTML
            lotes_html = []
            lotes_originais = self.selected_leilao.get('lotes', [])
            titulo_leilao = self.selected_leilao.get('leilao_titulo', 'Relatório de Leilão')
            
            for lote in lotes_originais:
                # Limpar valor (remover R$ para o template adicionar)
                valor = lote.get('valor_leilao', '') or lote.get('valor_minimo', '')
                valor_limpo = valor.replace('R$', '').strip()
                if not valor_limpo:
                    valor_limpo = "0,00"

                # Extrair número
                num_str = lote.get('numero_lote', '0').upper().replace('LOTE', '').strip()
                
                lotes_html.append({
                    "numero": num_str,
                    "titulo": self.limpar_titulo(lote, titulo_leilao),
                    "descricao": lote.get('descricao', '') or "Sem descrição detalhada.",
                    "lances": 0, # Dado não disponível no JSON atual
                    "valorMinimo": valor_limpo,
                    "localizacao": "Paraíba", # Padrão
                    "imagem": lote.get('imagem_lote', ''),
                    "retirado": False
                })

            # Ler template
            with open(ARQUIVO_TEMPLATE, 'r', encoding='utf-8') as f:
                html_content = f.read()

            # Substituir dados no HTML
            # 1. Substituir array de lotes
            json_lotes = json.dumps(lotes_html, ensure_ascii=False)
            # Escapar backslashes para que o re.sub não os interprete (necessário para \n funcionar no JS)
            json_lotes = json_lotes.replace('\\', '\\\\')
            
            html_content = re.sub(
                r'const lotes = \[.*?\];', 
                f'const lotes = {json_lotes};', 
                html_content, 
                flags=re.DOTALL
            )

            # 2. Substituir Título do Leilão
            html_content = html_content.replace('>Leilão Exemplo<', f'>{titulo_leilao}<')
            
            # 3. Substituir Total de Lotes
            html_content = re.sub(
                r'<span id="totalLotes">.*?</span>',
                f'<span id="totalLotes">{len(lotes_html)}</span>',
                html_content
            )

            # 4. Substituir Data
            data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
            html_content = re.sub(
                r'<span id="dataAbertura">.*?</span>',
                f'<span id="dataAbertura">{data_hoje}</span>',
                html_content
            )

            # 5. Substituir Logo do Comitente
            logo_url = self.selected_leilao.get('comitente_logo', '')
            if logo_url:
                # Substituir no header
                html_content = html_content.replace(
                    'https://via.placeholder.com/60x60?text=Logo', 
                    logo_url
                )
                # Substituir na tabela (template string do JS)
                html_content = html_content.replace(
                    'https://via.placeholder.com/30x30?text=C', 
                    logo_url
                )

            # 6. Substituir Imagens dos Lotes (feito via JS no template, mas precisamos garantir que o JS use o campo 'imagem')
            # O template atual usa: <img src="https://via.placeholder.com/100x75?text=Foto" ... />
            # Vamos alterar o template JS para usar ${lote.imagem || 'placeholder'}
            
            html_content = html_content.replace(
                'src="https://via.placeholder.com/100x75?text=Foto"',
                'src="${lote.imagem || \'https://via.placeholder.com/100x75?text=Foto\'}"'
            )

            # Nome do arquivo sugerido
            nome_base = f"Relatorio_{titulo_leilao.replace(' ', '_').replace('/', '-')}"
            nome_limpo = "".join([c for c in nome_base if c.isalpha() or c.isdigit() or c in (' ', '.', '_', '-')]).strip()
            
            return html_content, nome_limpo

        except Exception as ex:
            self.mostrar_mensagem(f"Erro ao preparar dados: {ex}", erro=True)
            return None, None

    def gerar_relatorio_html(self, e):
        html_content, nome_base = self._gerar_conteudo_html()
        if not html_content:
            return

        try:
            nome_arquivo = f"{nome_base}.html"
            with open(nome_arquivo, 'w', encoding='utf-8') as f:
                f.write(html_content)

            self.mostrar_mensagem(f"Relatório HTML gerado: {nome_arquivo}")
            try:
                os.startfile(nome_arquivo)
            except:
                pass
        except Exception as ex:
            self.mostrar_mensagem(f"Erro ao salvar HTML: {ex}", erro=True)

    def iniciar_geracao_pdf(self, e):
        html_content, nome_base = self._gerar_conteudo_html()
        if not html_content:
            return
        
        self.temp_html_content = html_content # Guardar para usar no callback
        self.file_picker.save_file(
            dialog_title="Salvar Relatório PDF",
            file_name=f"{nome_base}.pdf",
            allowed_extensions=["pdf"]
        )

    def concluir_geracao_pdf(self, e: ft.FilePickerResultEvent):
        if not e.path:
            return # Cancelado pelo usuário
            
        try:
            self.mostrar_mensagem("Gerando PDF... Aguarde.")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_content(self.temp_html_content)
                page.pdf(path=e.path, format="A4", print_background=True, margin={"top": "1cm", "right": "1cm", "bottom": "1cm", "left": "1cm"})
                browser.close()
                
            self.mostrar_mensagem(f"PDF salvo com sucesso em: {e.path}")
            try:
                os.startfile(e.path)
            except:
                pass
                
        except Exception as ex:
            self.mostrar_mensagem(f"Erro ao gerar PDF: {ex}", erro=True)
        finally:
            self.temp_html_content = None

    def buscar_leiloes_online(self, e):
        pass # Removido

    def importar_leilao_url(self, e):
        url = self.input_url.value
        if not url:
            self.mostrar_mensagem("Por favor, insira uma URL válida.", erro=True)
            return
        if self.scraper_running:
            self.mostrar_mensagem("Aguarde o processo atual terminar.", erro=True)
            return
        
        self.executar_scraper(["--url", url], f"Importando leilão: {url}...")
        self.input_url.value = ""
        self.page.update()

    def baixar_leilao(self, url):
        if self.scraper_running:
            self.mostrar_mensagem("Aguarde o processo atual terminar.", erro=True)
            return
        self.executar_scraper(["--url", url], "Baixando dados do leilão...")

    def executar_scraper(self, args, msg):
        self.scraper_running = True
        self.btn_importar.disabled = True
        self.progress_bar.visible = True
        self.status_text.value = msg
        self.page.update()

        thread = threading.Thread(target=self._executar_scraper_thread, args=(args,))
        thread.start()

    def _executar_scraper_thread(self, args):
        try:
            # Executa o script python com argumentos
            cmd = ['python', ARQUIVO_SCRAPER] + args
            process = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace'
            )
            
            if process.returncode == 0:
                self._scraper_concluido(sucesso=True)
            else:
                erro_msg = process.stderr
                self._scraper_concluido(sucesso=False, msg=erro_msg)
                
        except Exception as e:
            self._scraper_concluido(sucesso=False, msg=str(e))

    def _scraper_concluido(self, sucesso, msg=""):
        self.scraper_running = False
        self.btn_importar.disabled = False
        self.progress_bar.visible = False
        
        if sucesso:
            self.status_text.value = "Dados atualizados com sucesso!"
            self.carregar_dados()
            self.mostrar_mensagem("Dados atualizados com sucesso!")
        else:
            self.status_text.value = "Erro na atualização."
            self.mostrar_mensagem(f"Erro ao rodar scraper: {msg}", erro=True)
        
        self.page.update()

    def mostrar_mensagem(self, texto, erro=False):
        snack = ft.SnackBar(
            content=ft.Text(texto),
            bgcolor=ft.Colors.RED_600 if erro else ft.Colors.GREEN_600
        )
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()

def main(page: ft.Page):
    app = SistemaLeiloes(page)

if __name__ == "__main__":
    ft.app(target=main)
