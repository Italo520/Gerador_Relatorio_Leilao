import flet as ft
import json
import os
import subprocess
import re
import threading
from datetime import datetime
import shutil
from playwright.sync_api import sync_playwright
import queue
import scraper
import io
import sys
from contextlib import redirect_stdout, redirect_stderr

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# Configurações
ARQUIVO_JSON = 'leiloes_completo.json'
ARQUIVO_TEMPLATE = resource_path('Relatório Leilões.html')
ARQUIVO_SCRAPER = 'scraper.py'

class StreamToQueue:
    def __init__(self, queue):
        self.queue = queue
    def write(self, buf):
        for line in buf.splitlines():
            if line.strip():
                self.queue.put(line.strip())
    def flush(self):
        pass

class SistemaLeiloes:
    def __init__(self, page: ft.Page):
        self.page = page
        self.setup_page()
        
        self.leiloes_data = []
        self.leiloes_online = []
        self.avaliacoes = {} # Dicionário para armazenar avaliações manuais: {lote_url_ou_id: valor}
        self.selected_leilao = None
        self.scraper_running = False
        self.log_visible = False  # Controlar visibilidade do log
        self.log_queue = queue.Queue()  # Fila para mensagens de log thread-safe
        self.log_timer = None  # Timer para atualizar log periodicamente
        
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

        # Área de Log
        self.log_text = ft.TextField(
            value="",
            multiline=True,
            read_only=True,
            min_lines=10,
            max_lines=10,
            text_size=11,
            bgcolor=ft.Colors.BLACK,
            color=ft.Colors.GREEN_300,
            border_color=ft.Colors.GREY_700,
            visible=False
        )
        
        self.btn_toggle_log = ft.IconButton(
            icon=ft.Icons.TERMINAL,
            icon_color=ft.Colors.GREY_600,
            tooltip="Mostrar/Ocultar Log",
            on_click=self.toggle_log,
            visible=False
        )

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
                    ft.Row([
                        self.status_text,
                        self.btn_toggle_log,
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.log_text,
                    
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

            # Botão de Excluir
            btn_excluir = ft.IconButton(
                icon=ft.Icons.DELETE_OUTLINE,
                icon_color=ft.Colors.RED_400,
                tooltip="Excluir este leilão",
                on_click=lambda e, u=url: self.excluir_leilao(u)
            )

            card_content = ft.Row([
                icon,
                ft.Column([
                    ft.Text(titulo, weight=ft.FontWeight.BOLD, size=13, width=130, no_wrap=False, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(sub_text, size=11, color=ft.Colors.GREY_600)
                ], expand=True, spacing=2),
                ft.Row([btn_baixar, btn_excluir], spacing=0)
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

    def _gerar_conteudo_html(self):
        if not self.selected_leilao:
            return None, None

    def mostrar_detalhes_leilao(self):
        try:
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
                    ft.DataColumn(ft.Text("Título")),
                    ft.DataColumn(ft.Text("Avaliação")), # Nova coluna
                    ft.DataColumn(ft.Text("Valor")),
                    ft.DataColumn(ft.Text("Link")),
                ],
                rows=[],
                border=ft.border.all(1, ft.Colors.GREY_200),
                vertical_lines=ft.border.BorderSide(1, ft.Colors.GREY_200),
                horizontal_lines=ft.border.BorderSide(1, ft.Colors.GREY_200),
            )

            # Função auxiliar para extrair número do lote para ordenação
            def extrair_numero_lote(lote):
                try:
                    num_str = lote.get('numero_lote', '0').replace('LOTE', '').strip()
                    return int(re.sub(r'\D', '', num_str)) if num_str else 0
                except:
                    return 0

            # Ordenar lotes
            lotes.sort(key=extrair_numero_lote)

            for lote in lotes:
                titulo_lote = self.limpar_titulo(lote, titulo)
                valor = lote.get('valor_leilao', '') or lote.get('valor_minimo', '')
                
                tabela.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(ft.Text(lote.get('numero_lote', '').replace('LOTE ', ''))),
                            ft.DataCell(ft.Text(titulo_lote, weight=ft.FontWeight.BOLD)),
                            ft.DataCell(ft.TextField(
                                value=self.avaliacoes.get(lote.get('url') or lote.get('numero_lote'), ''),
                                width=100,
                                height=30,
                                text_size=12,
                                content_padding=5,
                                on_change=lambda e, l=lote: self.atualizar_avaliacao(e, l)
                            )),
                            ft.DataCell(ft.Text(valor)),
                            ft.DataCell(ft.IconButton(
                                icon=ft.Icons.OPEN_IN_NEW,
                                tooltip="Abrir no navegador",
                                url=lote.get('url'),
                                icon_size=20
                            )),
                        ]
                    )
                )

            aviso = ft.Container()

            self.content_area.controls.extend([
                header_detalhes,
                ft.Divider(),
                ft.Text("Pré-visualização dos Lotes:", weight=ft.FontWeight.BOLD),
                ft.Column([tabela, aviso], scroll=ft.ScrollMode.AUTO, expand=True)
            ])
            
            self.page.update()
            
        except Exception as e:
            print(f"Erro ao mostrar detalhes: {e}")
            self.content_area.controls.append(ft.Text(f"Erro ao carregar detalhes: {e}", color=ft.Colors.RED))
            self.page.update()

    def limpar_titulo(self, lote, titulo_leilao):
        """Melhora o título do lote se ele for igual ao do leilão"""
        titulo = lote.get('titulo', '')
        num_str = lote.get('numero_lote', '').replace('LOTE', '').strip()
        
        # Se o título do lote for genérico ou igual ao do leilão, tenta extrair da URL ou descrição
        if not titulo or titulo == titulo_leilao or titulo == "Título não encontrado" or titulo == "LOTE":
            # Tenta extrair da descrição
            descricao = lote.get('descricao', '')
            if descricao:
                linhas = [l.strip() for l in descricao.split('\n') if l.strip()]
                
                # Palavras-chave para ignorar no início das linhas
                ignorar = [
                    "DESCRIÇÃO", "AVALIAÇÃO", "LEILOEIRO", "COMITENTE", "CÓDIGO LEILÃO", 
                    "CÓDIGO LOTE", "NÚMERO LOTE", "HABILITADOS", "TIPO", "RECEBIMENTO DE LANCES",
                    "LOCALIZAÇÃO", "VISITAÇÃO", "PAGAMENTO", "RETIRADA"
                ]
                
                for linha in linhas:
                    linha_upper = linha.upper()
                    # Se a linha for apenas uma palavra-chave, ignora
                    if any(linha_upper == kw or linha_upper.startswith(f"{kw}:") for kw in ignorar):
                        continue

                    # Se a linha contiver "LOTE:" e "DATA:", ignora (cabeçalho padrão)
                    if "LOTE:" in linha_upper and "DATA:" in linha_upper:
                        continue
                    
                    # Se a linha for um valor monetário isolado, ignora
                    if re.match(r'^R\$\s?[\d\.,]+$', linha):
                        continue
                        
                    # Se a linha for muito curta (menos de 3 chars) e não for alfanumérica, ignora
                    if len(linha) < 3:
                        continue
                        
                    # Achamos um candidato!
                    return linha

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
                    
            # Se tudo falhar, retorna LOTE X
            if num_str:
                return f"LOTE {num_str}"
                
        return titulo

    def atualizar_avaliacao(self, e, lote):
        """Atualiza o valor da avaliação no dicionário"""
        chave = lote.get('url') or lote.get('numero_lote')
        if chave:
            self.avaliacoes[chave] = e.control.value


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
            
            # Ordenar lotes também para o relatório
            def extrair_numero_lote(lote):
                try:
                    num_str = lote.get('numero_lote', '0').replace('LOTE', '').strip()
                    return int(re.sub(r'\D', '', num_str)) if num_str else 0
                except:
                    return 0
            
            lotes_originais.sort(key=extrair_numero_lote)

            titulo_leilao = self.selected_leilao.get('leilao_titulo', 'Relatório de Leilão')
            
            for lote in lotes_originais:
                # Limpar valor (remover R$ para o template adicionar)
                valor = lote.get('valor_leilao', '') or lote.get('valor_minimo', '')
                valor_limpo = valor.replace('R$', '').strip()
                if not valor_limpo:
                    valor_limpo = "0,00"

                # Extrair número (manter "LOTE" se existir, ou adicionar se for apenas número)
                raw_num = lote.get('numero_lote', '0').upper().strip()
                if "LOTE" not in raw_num:
                    num_str = f"LOTE {raw_num}"
                else:
                    num_str = raw_num
                
                # Extrair apenas o número para a bolinha
                apenas_numero = num_str.replace('LOTE', '').strip()
                
                titulo_limpo = self.limpar_titulo(lote, titulo_leilao)
                if titulo_limpo.upper() == "LOTE" or not titulo_limpo.strip():
                    titulo_limpo = num_str # Já é "LOTE X"

                lotes_html.append({
                    "numero": apenas_numero,
                    "titulo": titulo_limpo,
                    "descricao": lote.get('descricao', '') or "Sem descrição detalhada.",
                    "lances": 0, # Dado não disponível no JSON atual
                    "valorMinimo": valor_limpo,
                    "avaliacao": self.avaliacoes.get(lote.get('url') or lote.get('numero_lote'), ''), # Incluir avaliação
                    "localizacao": "Paraíba", # Padrão
                    "imagem": lote.get('imagem_lote', ''),
                    "comitente": lote.get('simbolo_lote', ''),
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

            # 5.1. Substituir Logo do LeiloesPB no cabeçalho
            try:
                logo_leiloespb_path = 'logo_leiloespb'
                if os.path.exists(logo_leiloespb_path):
                    import base64
                    with open(logo_leiloespb_path, 'rb') as img_file:
                        logo_base64 = base64.b64encode(img_file.read()).decode('utf-8')
                        # Detectar tipo de imagem (assumindo PNG por padrão)
                        logo_data_uri = f'data:image/png;base64,{logo_base64}'
                        # Substituir a URL da logo do LeiloesPB
                        html_content = html_content.replace(
                            'https://www.leiloespb.com.br/client/logo.png?v=2',
                            logo_data_uri
                        )
            except Exception as e:
                print(f"Aviso: Não foi possível carregar logo_leiloespb: {e}")

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

    def excluir_leilao(self, url):
        """Remove um leilão da lista e do arquivo JSON"""
        # Encontrar e remover da lista em memória
        self.leiloes_data = [l for l in self.leiloes_data if l.get('leilao_url') != url]
        
        # Salvar no arquivo JSON
        try:
            with open(ARQUIVO_JSON, 'w', encoding='utf-8') as f:
                json.dump(self.leiloes_data, f, ensure_ascii=False, indent=4)
            
            self.mostrar_mensagem("Leilão removido com sucesso!")
            
            # Se o leilão removido era o selecionado, limpar seleção
            if self.selected_leilao and self.selected_leilao.get('leilao_url') == url:
                self.selected_leilao = None
                self.main_container.content = ft.Text("Selecione um leilão para visualizar os detalhes.", size=16, color=ft.Colors.GREY_500)
            
            self.atualizar_lista_leiloes()
            
        except Exception as e:
            self.mostrar_mensagem(f"Erro ao salvar alterações: {e}", erro=True)

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
        
        # Limpar e mostrar log
        self.limpar_log()
        self.log_visible = True
        self.log_text.visible = True
        self.btn_toggle_log.visible = True
        
        # Iniciar processamento da fila de log
        self.processar_fila_log()
        
        self.page.update()

        thread = threading.Thread(target=self._executar_scraper_thread, args=(args,))
        thread.start()

    def _executar_scraper_thread(self, args):
        try:
            # Redirecionar stdout e stderr para a fila de log
            stream = StreamToQueue(self.log_queue)
            
            with redirect_stdout(stream), redirect_stderr(stream):
                scraper.run_scraper(args)
            
            self._scraper_concluido(sucesso=True)
                
        except Exception as e:
            self._scraper_concluido(sucesso=False, msg=str(e))

    def _scraper_concluido(self, sucesso, msg=""):
        self.scraper_running = False
        self.btn_importar.disabled = False
        self.progress_bar.visible = False
        
        # Cancelar timer se ainda estiver rodando
        if self.log_timer:
            try:
                self.log_timer.cancel()
            except:
                pass
        
        # Processar mensagens finais da fila
        try:
            while not self.log_queue.empty():
                msg_log = self.log_queue.get_nowait()  
                timestamp = datetime.now().strftime("%H:%M:%S")
                linhas = self.log_text.value.split('\n') if self.log_text.value else []
                linhas.append(f"[{timestamp}] {msg_log}")
                self.log_text.value = '\n'.join(linhas[-500:])
        except:
            pass
        
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

    def toggle_log(self, e):
        """Alterna a visibilidade do log"""
        self.log_visible = not self.log_visible
        self.log_text.visible = self.log_visible
        self.page.update()

    def adicionar_log(self, mensagem):
        """Adiciona uma mensagem ao log (thread-safe)"""
        try:
            # Colocar mensagem na fila
            self.log_queue.put(mensagem)
        except:
            pass
    
    def processar_fila_log(self):
        """Processa mensagens da fila e atualiza o log (executado na thread principal)"""
        try:
            mensagens_novas = []
            # Pegar todas as mensagens disponíveis
            while not self.log_queue.empty():
                try:
                    msg = self.log_queue.get_nowait()
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    mensagens_novas.append(f"[{timestamp}] {msg}")
                except queue.Empty:
                    break
            
            if mensagens_novas:
                # Adicionar ao log existente
                linhas_atuais = self.log_text.value.split('\n') if self.log_text.value else []
                linhas_atuais.extend(mensagens_novas)
                
                # Manter últimas 500 linhas
                if len(linhas_atuais) > 500:
                    linhas_atuais = linhas_atuais[-500:]
                
                self.log_text.value = '\n'.join(linhas_atuais)
                self.page.update()
            
            # Continuar processando se scraper ainda está rodando
            if self.scraper_running:
                self.log_timer = threading.Timer(0.5, self.processar_fila_log)
                self.log_timer.start()
        except Exception as e:
            print(f"Erro ao processar log: {e}")

    def limpar_log(self):
        """Limpa o conteúdo do log"""
        self.log_text.value = ""
        self.page.update()


def main(page: ft.Page):
    app = SistemaLeiloes(page)

if __name__ == "__main__":
    ft.app(target=main)
