import json
import time
from playwright.sync_api import sync_playwright
import argparse
import sys
import os

# Forçar encoding UTF-8 no Windows para evitar erros de impressão
if sys.platform == "win32":
    if sys.stdout is not None:
        sys.stdout.reconfigure(encoding='utf-8')
    if sys.stderr is not None:
        sys.stderr.reconfigure(encoding='utf-8')

BASE_URL = "https://www.leiloespb.com.br"

def extrair_dados_lote_individual(page, lote_url):
    """
    Extrai dados de um lote individual quando já estamos na página dele.
    Usado para leilões com apenas 1 lote que redirecionam diretamente.
    """
    try:
        page.wait_for_timeout(500)
        
        # Extrair título do lote
        titulo = "Título não encontrado"
        try:
            titulo_locator = page.locator('h2').first
            if titulo_locator.count() > 0:
                titulo = titulo_locator.inner_text(timeout=3000).strip()
            else:
                titulo_locator = page.locator('h1').first
                if titulo_locator.count() > 0:
                    titulo = titulo_locator.inner_text(timeout=3000).strip()
        except:
            titulo = lote_url.split('/')[-1].replace('-', ' ').title()
        
        # Extrair descrição - XPath específico para lote único
        descricao = "Descrição não disponível"
        try:
            # Tentativa 1: XPath completo fornecido pelo usuário
            desc_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[6]')
            if desc_locator.count() > 0:
                descricao = desc_locator.inner_text(timeout=3000).strip()
            else:
                # Tentativa 2: XPath do parágrafo específico
                desc_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[6]/p')
                if desc_locator.count() > 0:
                    descricao = desc_locator.inner_text(timeout=3000).strip()
                else:
                    # Tentativa 3: Fallback genérico
                    desc_heading = page.locator('text="Descrição"').first
                    if desc_heading.count() > 0:
                        desc_container = desc_heading.locator('xpath=..').locator('xpath=following-sibling::*').first
                        if desc_container.count() > 0:
                            descricao = desc_container.inner_text(timeout=3000).strip()
        except:
            pass
        
        # Extrair valor mínimo de venda
        valor_minimo = "Sob Consulta"
        try:
            valor_locator = page.locator('text="Valor mínimo de venda"').locator('xpath=following-sibling::*').first
            if valor_locator.count() > 0:
                valor_minimo = valor_locator.inner_text(timeout=3000).strip()
        except:
            pass
        
        # Extrair valor do leilão
        valor_leilao = "Não informado"
        try:
            leilao_valor = page.locator('text=/Leilão Único|1º Leilão/').locator('xpath=following::*[contains(text(), "R$")]').first
            if leilao_valor.count() > 0:
                valor_leilao = leilao_valor.inner_text(timeout=3000).strip()
        except:
            pass
        
        # Extrair código do lote
        codigo_lote = "N/A"
        try:
            codigo_locator = page.locator('text="Código Lote"').locator('xpath=following-sibling::*').first
            if codigo_locator.count() > 0:
                codigo_lote = codigo_locator.inner_text(timeout=3000).strip()
        except:
            pass
        
        # Extrair número do lote
        numero_lote = "N/A"
        try:
            numero_locator = page.locator('text="Número Lote"').locator('xpath=following-sibling::*').first
            if numero_locator.count() > 0:
                numero_lote = numero_locator.inner_text(timeout=3000).strip()
        except:
            pass
        
        # Extrair símbolo/logo do lote - XPath específico para lote único
        simbolo_lote = ""
        try:
            # XPath específico fornecido pelo usuário para o símbolo
            simbolo_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[5]/ul[1]/li[2]/div[1]/img')
            if simbolo_locator.count() > 0:
                src = simbolo_locator.get_attribute('src')
                if src:
                    simbolo_lote = src if src.startswith('http') else BASE_URL + src
        except:
            pass
        
        except:
            pass
        
        # Extrair imagem do lote (foto principal)
        imagem_lote = ""
        try:
            # Tentar vários seletores
            seletores_imagem = [
                'xpath=/html/body/section[4]/div/div[2]/div/div[1]/div/div[2]/div[1]/div/div/div[2]/div/div/a/img',
                '.product-gallery-preview img',
                'div.image-container img',
                '.gallery img',
                '.product-image img',
                'img[alt*="lote"]',
                'img[alt*="veículo"]',
                'img[alt*="veiculo"]',
                'section img',
                'main img'
            ]
            
            for seletor in seletores_imagem:
                img_locator = page.locator(seletor).first
                if img_locator.count() > 0:
                    src = img_locator.get_attribute('src')
                    if src and 'placeholder' not in src.lower():
                        imagem_lote = src if src.startswith('http') else BASE_URL + src
                        break
        except:
            pass
        
        # Extrair status retirado
        retirado = False
        try:
            # XPath específico fornecido para status retirado
            status_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[2]/div/div[1]/ul[3]/li[2]/div[2]/strong')
            if status_locator.count() > 0:
                texto_status = status_locator.inner_text(timeout=3000).strip().lower()
                if "retirado" in texto_status:
                    retirado = True
        except:
            pass
        
        return {
            "codigo_lote": codigo_lote,
            "numero_lote": numero_lote,
            "titulo": titulo,
            "descricao": descricao,
            "valor_leilao": valor_leilao,
            "valor_minimo": valor_minimo,
            "simbolo_lote": simbolo_lote,
            "imagem_lote": imagem_lote,
            "retirado": retirado,
            "url": lote_url
        }
    except Exception as e:
        print(f"   Erro ao extrair lote individual: {str(e)[:50]}")
        return None

def extrair_lotes_de_leilao(page):
    """
    Extrai informações de todos os lotes de um leilão específico.
    """
    lotes_data = []
    
    # Verificar se foi redirecionado direto para página de lote (leilão com 1 único lote)
    url_atual = page.url
    comitente_logo_encontrado = ""  # Variável para armazenar a logo do comitente
    
    if '/lote/' in url_atual and url_atual.count('/') >= 7:
        print("   Leilão com lote único detectado (redirecionamento direto)")
        # Extrair dados deste único lote
        lote_info = extrair_dados_lote_individual(page, url_atual)
        if lote_info:
            lotes_data.append(lote_info)
            # A logo do comitente está no mesmo lugar que o símbolo do lote
            comitente_logo_encontrado = lote_info.get('simbolo_lote', '')
            print(f"   ✓ 1 lote coletado")
        return lotes_data, comitente_logo_encontrado
    
    # Aguardar um seletor específico ao invés de networkidle
    try:
        page.wait_for_selector('article', timeout=10000)
    except:
        print("   ⚠ Nenhum lote encontrado nesta página")
        return lotes_data, comitente_logo_encontrado
    
    # Coletar URLs e imagens de todas as páginas
    lotes_info = {}  # {url: imagem}
    pagina_atual = 1
    paginas_vazias_consecutivas = 0  # Contador para detectar loop infinito
    
    while True:
        print(f"   Coletando lotes da página {pagina_atual}...")
        
        # Coletar lotes dos cards article da página atual
        lotes_cards = page.locator('article')
        count = lotes_cards.count()
        
        lotes_encontrados_nesta_pagina = 0
        for i in range(count):
            try:
                card = lotes_cards.nth(i)
                
                # Procurar link do lote dentro do article
                link = card.locator('a[href*="/lote/"]').first
                if link.count() > 0:
                    href = link.get_attribute('href')
                    if href and not any(x in href for x in ['facebook', 'twitter', 'whatsapp', 'mailto', 'login']):
                        url_completa = href if href.startswith('http') else BASE_URL + href
                        # Garantir que é uma URL de lote individual
                        if '/lote/' in url_completa and url_completa.count('/') >= 6:
                            # Extrair imagem do card
                            imagem = ""
                            try:
                                # Tentar pegar a imagem dentro do article
                                img = card.locator('img').first
                                if img.count() > 0:
                                    imagem = img.get_attribute('src') or ""
                            except:
                                pass
                            
                            if url_completa not in lotes_info:
                                lotes_info[url_completa] = imagem
                                lotes_encontrados_nesta_pagina += 1
            except:
                continue
        
        print(f"      {lotes_encontrados_nesta_pagina} novos lotes encontrados")
        
        # Verificar se encontrou lotes novos
        if lotes_encontrados_nesta_pagina == 0:
            paginas_vazias_consecutivas += 1
            print(f"      ⚠ Nenhum lote novo ({paginas_vazias_consecutivas} páginas vazias consecutivas)")
            # Se 3 páginas consecutivas não encontrarem lotes novos, parar
            if paginas_vazias_consecutivas >= 3:
                print(f"   ⚠ Parando paginação: {paginas_vazias_consecutivas} páginas consecutivas sem lotes novos")
                break
        else:
            # Resetar contador se encontrou lotes
            paginas_vazias_consecutivas = 0
        
        # Tentar encontrar botão de próxima página
        conseguiu_paginar = False
        try:
            # Scroll até o final da página
            page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            page.wait_for_timeout(500)
            
            # Estratégias para encontrar o botão "Próxima"
            botao_next = None
            
            # 1. Tentar pelo seletor baseado na estrutura da screenshot (.row-actions .c-right li.arrow-right a)
            # A classe arrow-right geralmente indica o botão "próximo" neste template
            candidatos = page.locator('.row-actions .c-right li.arrow-right a')
            if candidatos.count() > 0:
                botao_next = candidatos.first
            
            # 2. Fallback: procurar qualquer link dentro de um li.arrow-right
            if not botao_next or botao_next.count() == 0:
                candidatos = page.locator('li.arrow-right a')
                if candidatos.count() > 0:
                    botao_next = candidatos.last
            
            # 3. Fallback: procurar por ícone de seta (fa-angle-right ou similar)
            if not botao_next or botao_next.count() == 0:
                setas = page.locator('.pagination a:has(i.fa-angle-right), .pagination a:has(i.fa-chevron-right)')
                if setas.count() > 0:
                    botao_next = setas.last

            # 4. Fallback: Tentar clicar no número da próxima página
            if not botao_next or botao_next.count() == 0:
                # Encontrar o item ativo
                ativo = page.locator('.pagination li.active, .pagination li.current').first
                if ativo.count() > 0:
                    # Tentar o próximo irmão
                    proximo = ativo.locator('xpath=following-sibling::li[1]/a')
                    if proximo.count() > 0:
                        botao_next = proximo.first

            # Executar clique se encontrou
            if botao_next and botao_next.count() > 0:
                if botao_next.is_visible():
                    print(f"   Navegando para página {pagina_atual + 1}...")
                    url_antes = page.url
                    
                    # Forçar clique via JS se o elemento estiver coberto ou difícil de clicar
                    try:
                        botao_next.click(timeout=2000)
                    except:
                        page.evaluate('(element) => element.click()', botao_next.element_handle())
                    
                    page.wait_for_timeout(2000)
                    
                    # Verificar mudança
                    if page.url != url_antes:
                        pagina_atual += 1
                        conseguiu_paginar = True
                    else:
                        # Se a URL não mudou, verificar se o conteúdo mudou (AJAX)
                        # Esperar um pouco mais e verificar se novos artigos apareceram
                        page.wait_for_timeout(1000)
                        pagina_atual += 1 # Assumir que mudou se não houve erro, para tentar continuar
                        conseguiu_paginar = True
            
        except Exception as e:
            print(f"   Erro ao tentar paginar: {str(e)[:100]}")
        
        if not conseguiu_paginar:
            print(f"   Fim da paginação na página {pagina_atual}")
            break
    
    print(f"   Total de {len(lotes_info)} lotes únicos coletados de {pagina_atual} página(s)")
    
    # Iterar sobre cada lote
    for idx, (lote_url, imagem_card) in enumerate(sorted(lotes_info.items()), 1):
        try:
            print(f"      [{idx}/{len(lotes_info)}] Processando: {lote_url.split('/')[-1][:40]}...", end='')
            
            # Navegar para a página do lote - usar domcontentloaded é mais rápido
            page.goto(lote_url, wait_until="domcontentloaded", timeout=30000)
            
            # Esperar um tempo menor
            page.wait_for_timeout(800)
            
            # Extrair título do lote (H2 principal ou H1)
            titulo = "Título não encontrado"
            try:
                # Tentar H2 primeiro
                titulo_locator = page.locator('h2').first
                if titulo_locator.count() > 0:
                    titulo = titulo_locator.inner_text(timeout=3000).strip()
                else:
                    # Fallback para H1
                    titulo_locator = page.locator('h1').first
                    if titulo_locator.count() > 0:
                        titulo = titulo_locator.inner_text(timeout=3000).strip()
            except:
                # Se falhar, tentar pegar do slug da URL
                titulo = lote_url.split('/')[-1].replace('-', ' ').title()
            
            # Extrair descrição
            descricao = "Descrição não disponível"
            try:
                # Tentativa 1: XPath completo fornecido pelo usuário (div inteira)
                desc_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[6]')
                if desc_locator.count() > 0:
                    descricao = desc_locator.inner_text(timeout=3000).strip()
                else:
                    # Tentativa 2: XPath do parágrafo específico
                    desc_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[6]/p')
                    if desc_locator.count() > 0:
                        descricao = desc_locator.inner_text(timeout=3000).strip()
                    else:
                        # Tentativa 3: Fallback genérico
                        desc_heading = page.locator('text="Descrição"').first
                        if desc_heading.count() > 0:
                            desc_container = desc_heading.locator('xpath=..').locator('xpath=following-sibling::*').first
                            if desc_container.count() > 0:
                                descricao = desc_container.inner_text(timeout=3000).strip()
            except:
                pass
            
            # Extrair valor mínimo de venda
            valor_minimo = "Sob Consulta"
            try:
                valor_locator = page.locator('text="Valor mínimo de venda"').locator('xpath=following-sibling::*').first
                if valor_locator.count() > 0:
                    valor_minimo = valor_locator.inner_text(timeout=3000).strip()
            except:
                pass
            
            # Extrair valor do leilão
            valor_leilao = "Não informado"
            try:
                leilao_valor = page.locator('text=/Leilão Único|1º Leilão/').locator('xpath=following::*[contains(text(), "R$")]').first
                if leilao_valor.count() > 0:
                    valor_leilao = leilao_valor.inner_text(timeout=3000).strip()
            except:
                pass
            
            # Extrair código do lote
            codigo_lote = "N/A"
            try:
                codigo_locator = page.locator('text="Código Lote"').locator('xpath=following-sibling::*').first
                if codigo_locator.count() > 0:
                    codigo_lote = codigo_locator.inner_text(timeout=3000).strip()
            except:
                pass
            
            # Extrair número do lote
            numero_lote = "N/A"
            try:
                numero_locator = page.locator('text="Número Lote"').locator('xpath=following-sibling::*').first
                if numero_locator.count() > 0:
                    numero_lote = numero_locator.inner_text(timeout=3000).strip()
            except:
                pass


            # Usar imagem já extraída do card da listagem
            imagem_lote = imagem_card
            
            # Extrair símbolo/logo do lote
            simbolo_lote = ""
            try:
                # XPath específico fornecido pelo usuário para o símbolo
                simbolo_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[5]/ul[1]/li[2]/div[1]/img')
                if simbolo_locator.count() > 0:
                    src = simbolo_locator.get_attribute('src')
                    if src:
                        simbolo_lote = src if src.startswith('http') else BASE_URL + src
            except:
                pass
            
            # Extrair status retirado
            retirado = False
            try:
                status_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[2]/div/div[1]/ul[3]/li[2]/div[2]/strong')
                if status_locator.count() > 0:
                    texto_status = status_locator.inner_text(timeout=3000).strip().lower()
                    if "retirado" in texto_status:
                        retirado = True
            except:
                pass
            
            lote_info = {
                "codigo_lote": codigo_lote,
                "numero_lote": numero_lote,
                "titulo": titulo,
                "descricao": descricao,
                "valor_leilao": valor_leilao,
                "valor_minimo": valor_minimo,
                "simbolo_lote": simbolo_lote,
                "imagem_lote": imagem_lote,
                "retirado": retirado,
                "url": lote_url
            }
            
            lotes_data.append(lote_info)
            
            # Capturar logo do comitente do primeiro lote processado
            if not comitente_logo_encontrado and simbolo_lote:
                comitente_logo_encontrado = simbolo_lote
            
            print(f" ✓")
            
            # Pausa mínima entre requisições
            time.sleep(0.1)
            
        except Exception as e:
            print(f" ✗ ({str(e)[:50]})")
            continue
    
    return lotes_data, comitente_logo_encontrado


def extrair_todos_os_leiloes(page):
    """
    Extrai todos os leilões da página principal e depois os lotes de cada um.
    """
    print(f"Acessando {BASE_URL}...")
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    
    # Esperar pelo container principal de leilões
    try:
        page.wait_for_selector('a[href*="/eventos/leilao/"]', timeout=10000)
        print("✓ Página principal carregada")
    except:
        print("✗ Timeout ao carregar página principal")
        return []
    
    page.wait_for_timeout(2000)
    
    # Buscar apenas os links principais dos cards de leilão
    leiloes_locators = page.locator('a[href*="/eventos/leilao/"]:has(h3)')
    count = leiloes_locators.count()
    
    print(f"✓ Encontrados {count} cards de leilões")
    
    leiloes_info = []
    for i in range(count):
        try:
            locator = leiloes_locators.nth(i)
            href = locator.get_attribute('href')
            
            if href:
                url_completa = href if href.startswith('http') else BASE_URL + href
                
                # Pegar o título do leilão (H3 dentro do card)
                try:
                    titulo_h3 = locator.locator('h3')
                    if titulo_h3.count() > 0:
                        titulo = titulo_h3.inner_text().strip()
                    else:
                        titulo = f"Leilão {url_completa.split('/')[-2]}"
                except:
                    titulo = f"Leilão {url_completa.split('/')[-2]}"
                
                # Evitar duplicatas
                if not any(l['url'] == url_completa for l in leiloes_info):
                    leiloes_info.append({
                        'url': url_completa,
                        'titulo': titulo if titulo else f"Leilão {len(leiloes_info)+1}"
                    })
                    print(f"   • {titulo}")
                    
        except Exception as e:
            continue
    
    print(f"\n✓ {len(leiloes_info)} leilões únicos identificados\n")
    
    resultados = []
    
    # Processar cada leilão
    for idx, leilao in enumerate(leiloes_info, 1):
        print(f"\n{'='*70}")
        print(f"[{idx}/{len(leiloes_info)}] {leilao['titulo']}")
        print(f"{'='*70}")
        
        try:
            # Navegar para a página do leilão
            page.goto(leilao['url'], wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)
            
            # Extrair lotes deste leilão (retorna também a logo do comitente)
            lotes, comitente_logo = extrair_lotes_de_leilao(page)
            
            # Se não encontrou logo nos lotes, tentar na página do leilão (fallback)
            if not comitente_logo:
                try:
                    logo_locator = page.locator('xpath=/html/body/section[2]/div/div/div[1]/a/div/img')
                    if logo_locator.count() > 0:
                        comitente_logo = logo_locator.get_attribute('src')
                except:
                    pass
            
            if lotes:
                resultados.append({
                    'leilao_titulo': leilao['titulo'],
                    'leilao_url': leilao['url'],
                    'comitente_logo': comitente_logo,
                    'total_lotes': len(lotes),
                    'lotes': lotes
                })
                print(f"   ✓ {len(lotes)} lotes extraídos")
            else:
                print("   ⚠ Nenhum lote encontrado")
                
        except Exception as e:
            print(f"   ✗ Erro ao processar leilão: {str(e)[:100]}")
            continue
            
    return resultados

def listar_leiloes_disponiveis(page):
    """
    Acessa a página principal e retorna lista de leilões disponíveis.
    Salva em leiloes_disponiveis.json
    """
    print(f"Acessando {BASE_URL}...")
    page.goto(BASE_URL, wait_until="domcontentloaded", timeout=30000)
    
    try:
        page.wait_for_selector('a[href*="/eventos/leilao/"]', timeout=10000)
    except:
        print("✗ Timeout ao carregar página principal")
        return []
    
    page.wait_for_timeout(2000)
    
    leiloes_locators = page.locator('a[href*="/eventos/leilao/"]:has(h3)')
    count = leiloes_locators.count()
    
    leiloes_online = []
    for i in range(count):
        try:
            locator = leiloes_locators.nth(i)
            href = locator.get_attribute('href')
            
            if href:
                url_completa = href if href.startswith('http') else BASE_URL + href
                
                try:
                    titulo_h3 = locator.locator('h3')
                    if titulo_h3.count() > 0:
                        titulo = titulo_h3.inner_text().strip()
                    else:
                        titulo = f"Leilão {url_completa.split('/')[-2]}"
                except:
                    titulo = f"Leilão {url_completa.split('/')[-2]}"
                
                if not any(l['url'] == url_completa for l in leiloes_online):
                    leiloes_online.append({
                        'url': url_completa,
                        'titulo': titulo
                    })
        except:
            continue
            
    # Salvar em arquivo temporário
    with open('leiloes_disponiveis.json', 'w', encoding='utf-8') as f:
        json.dump(leiloes_online, f, ensure_ascii=False, indent=4)
        
    return leiloes_online

def processar_leilao_unico(page, url):
    """
    Processa um único leilão e atualiza o JSON principal.
    """
    print(f"Processando leilão único: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    
    # Extrair título
    titulo = f"Leilão {url.split('/')[-2]}"
    try:
        titulo_el = page.locator('h1').first
        if titulo_el.count() > 0:
            titulo = titulo_el.inner_text().strip()
    except:
        pass
        
    lotes, comitente_logo = extrair_lotes_de_leilao(page)
    
    # Fallback para logo do comitente
    if not comitente_logo:
        try:
            logo_locator = page.locator('xpath=/html/body/section[2]/div/div/div[1]/a/div/img')
            if logo_locator.count() > 0:
                comitente_logo = logo_locator.get_attribute('src')
        except:
            pass
    
    novo_dado = {
        'leilao_titulo': titulo,
        'leilao_url': url,
        'comitente_logo': comitente_logo,
        'total_lotes': len(lotes),
        'lotes': lotes
    }
    
    # Carregar dados existentes
    dados_existentes = []
    if os.path.exists('leiloes_completo.json'):
        try:
            with open('leiloes_completo.json', 'r', encoding='utf-8') as f:
                dados_existentes = json.load(f)
        except:
            pass
            
    # Atualizar ou adicionar
    encontrado = False
    for i, item in enumerate(dados_existentes):
        # Verificar compatibilidade com chaves antigas e novas
        item_url = item.get('leilao_url') or item.get('url')
        if item_url == url:
            dados_existentes[i] = novo_dado
            encontrado = True
            break
            
    if not encontrado:
        dados_existentes.append(novo_dado)
        
    # Salvar
    with open('leiloes_completo.json', 'w', encoding='utf-8') as f:
        json.dump(dados_existentes, f, ensure_ascii=False, indent=4)
        
    print(f"✓ Dados salvos em leiloes_completo.json")

def run_scraper(args_list=None):
    parser = argparse.ArgumentParser(description='Scraper Leilões PB')
    parser.add_argument('--url', help='URL específica de um leilão para baixar')
    parser.add_argument('--listar', action='store_true', help='Apenas listar leilões disponíveis')
    
    if args_list:
        args = parser.parse_args(args_list)
    else:
        args = parser.parse_args()

    with sync_playwright() as p:
        print("Iniciando navegador...")
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            viewport={'width': 1366, 'height': 768}
        )
        page = context.new_page()
        
        try:
            if args.listar:
                listar_leiloes_disponiveis(page)
            elif args.url:
                processar_leilao_unico(page, args.url)
            else:
                # Modo padrão: baixar tudo
                dados = extrair_todos_os_leiloes(page)
                with open('leiloes_completo.json', 'w', encoding='utf-8') as f:
                    json.dump(dados, f, ensure_ascii=False, indent=4)
                print(f"✓ Extração concluída! Dados salvos em leiloes_completo.json")
                
        except Exception as e:
            print(f"Erro fatal: {e}")
        finally:
            print("Fechando navegador...")
            browser.close()

if __name__ == "__main__":
    run_scraper()
