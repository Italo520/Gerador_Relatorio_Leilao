import json
import time
from playwright.sync_api import sync_playwright
import argparse
import sys
import os

# Forçar encoding UTF-8 no Windows para evitar erros de impressão
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')

BASE_URL = "https://www.leiloespb.com.br"

def extrair_lotes_de_leilao(page):
    """
    Extrai informações de todos os lotes de um leilão específico.
    """
    lotes_data = []
    
    # Aguardar um seletor específico ao invés de networkidle
    try:
        page.wait_for_selector('article', timeout=10000)
    except:
        print("   ⚠ Nenhum lote encontrado nesta página")
        return lotes_data
    
    # Coletar URLs e imagens de todas as páginas
    lotes_info = {}  # {url: imagem}
    pagina_atual = 1
    
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
        
        # Tentar encontrar botão de próxima página
        try:
            # Procurar por botões de paginação comuns
            proxima_pagina = None
            
            # Tentar várias opções de seletores para "próxima página"
            seletores_proxima = [
                'a[rel="next"]',
                'a:has-text("Próxima")',
                'a:has-text("Next")',
                'a:has-text(">")',
                'button:has-text("Próxima")',
                '.pagination a:last-child',
                'nav[aria-label*="paginação"] a:last-child',
                'nav[aria-label*="pagination"] a:last-child'
            ]
            
            for seletor in seletores_proxima:
                try:
                    elemento = page.locator(seletor).first
                    if elemento.count() > 0:
                        # Verificar se não está desabilitado
                        classes = elemento.get_attribute('class') or ''
                        aria_disabled = elemento.get_attribute('aria-disabled') or ''
                        
                        if 'disabled' not in classes.lower() and aria_disabled != 'true':
                            proxima_pagina = elemento
                            break
                except:
                    continue
            
            if proxima_pagina:
                print(f"   Navegando para página {pagina_atual + 1}...")
                proxima_pagina.click()
                page.wait_for_timeout(2000)
                page.wait_for_selector('article', timeout=10000)
                pagina_atual += 1
            else:
                # Não há mais páginas
                break
                
        except:
            # Erro ao tentar paginar, assumir que não há mais páginas
            break
    
    print(f"   Total de {len(lotes_info)} lotes únicos coletados de {pagina_atual} página(s)")
    
    # Iterar sobre cada lote
    for idx, (lote_url, imagem_card) in enumerate(sorted(lotes_info.items()), 1):
        try:
            print(f"      [{idx}/{len(lotes_info)}] Processando: {lote_url.split('/')[-1][:40]}...", end='')
            
            # Navegar para a página do lote - usar domcontentloaded é mais rápido
            page.goto(lote_url, wait_until="domcontentloaded", timeout=30000)
            
            # Esperar um tempo fixo ao invés de aguardar seletor específico
            page.wait_for_timeout(2000)
            
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
            # Extrair descrição
            descricao = "Descrição não disponível"
            try:
                # Tentativa 1: XPath específico fornecido
                desc_locator = page.locator('xpath=/html/body/section[4]/div/div[2]/div/div[6]/p')
                if desc_locator.count() > 0:
                    descricao = desc_locator.inner_text(timeout=3000).strip()
                else:
                    # Tentativa 2: Fallback antigo
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
            
            lote_info = {
                "codigo_lote": codigo_lote,
                "numero_lote": numero_lote,
                "titulo": titulo,
                "descricao": descricao,
                "valor_leilao": valor_leilao,
                "valor_minimo": valor_minimo,
                "imagem_lote": imagem_lote,
                "url": lote_url
            }
            
            lotes_data.append(lote_info)
            print(f" ✓")
            
            # Pausa menor entre requisições
            time.sleep(0.3)
            
        except Exception as e:
            print(f" ✗ ({str(e)[:50]})")
            continue
    
    return lotes_data


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
            
            # Extrair lotes deste leilão
            # Extrair lotes deste leilão
            lotes = extrair_lotes_de_leilao(page)
            
            # Extrair logo do comitente
            comitente_logo = ""
            try:
                logo_locator = page.locator('xpath=/html/body/section[2]/div/div/div[1]/a/div/img')
                if logo_locator.count() > 0:
                    comitente_logo = logo_locator.get_attribute('src')
            except:
                pass

            resultados.append({
                'leilao_titulo': leilao['titulo'],
                'leilao_url': leilao['url'],
                'comitente_logo': comitente_logo,
                'total_lotes': len(lotes),
                'lotes': lotes
            })
            
            print(f"\n   ✓ Total extraído: {len(lotes)} lotes")
            
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
    
    print(f"✓ Encontrados {count} cards de leilões")
    
    leiloes_info = []
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
                
                if not any(l['url'] == url_completa for l in leiloes_info):
                    leiloes_info.append({
                        'url': url_completa,
                        'titulo': titulo
                    })
        except:
            continue
            
    # Salvar lista de disponíveis
    with open('leiloes_disponiveis.json', 'w', encoding='utf-8') as f:
        json.dump(leiloes_info, f, ensure_ascii=False, indent=2)
        
    print(f"✓ Lista de {len(leiloes_info)} leilões salva em leiloes_disponiveis.json")
    return leiloes_info


def processar_leilao_unico(page, url):
    """
    Processa um único leilão e atualiza o JSON principal.
    """
    print(f"Processando leilão: {url}")
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    page.wait_for_timeout(2000)
    # Extrair título (tentativa)
    titulo = "Leilão Importado"
    try:
        titulo_el = page.locator('h1').first
        if titulo_el.count() > 0:
            titulo = titulo_el.inner_text().strip()
    except:
        pass

    # Extrair logo do comitente
    comitente_logo = ""
    try:
        logo_locator = page.locator('xpath=/html/body/section[2]/div/div/div[1]/a/div/img')
        if logo_locator.count() > 0:
            comitente_logo = logo_locator.get_attribute('src')
    except:
        pass

    lotes = extrair_lotes_de_leilao(page)
    
    novo_dado = {
        'leilao_titulo': titulo,
        'leilao_url': url,
        'comitente_logo': comitente_logo,
        'total_lotes': len(lotes),
        'lotes': lotes
    }
    
    # Atualizar JSON principal
    dados_existentes = []
    if os.path.exists('leiloes_completo.json'):
        try:
            with open('leiloes_completo.json', 'r', encoding='utf-8') as f:
                dados_existentes = json.load(f)
        except:
            pass
            
    # Remover entrada antiga se existir (pela URL)
    dados_existentes = [d for d in dados_existentes if d.get('leilao_url') != url]
    dados_existentes.append(novo_dado)
    
    with open('leiloes_completo.json', 'w', encoding='utf-8') as f:
        json.dump(dados_existentes, f, ensure_ascii=False, indent=2)
        
    print(f"\n✓ Leilão '{titulo}' atualizado com {len(lotes)} lotes.")
    return novo_dado


def main():
    """
    Função principal que coordena a extração.
    """
    parser = argparse.ArgumentParser(description='Scraper de Leilões')
    parser.add_argument('--listar', action='store_true', help='Listar leilões disponíveis')
    parser.add_argument('--url', type=str, help='URL do leilão para raspar')
    args = parser.parse_args()

    print("\n" + "="*70)
    print(" SCRAPER DE LEILÕES - LEILÕES PB ".center(70))
    print("="*70 + "\n")
    
    with sync_playwright() as p:
        print("Iniciando navegador...")
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
                '--disable-gpu'
            ]
        )
        
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080}
        )
        
        page = context.new_page()
        page.set_default_timeout(30000)
        
        try:
            if args.listar:
                listar_leiloes_disponiveis(page)
            elif args.url:
                processar_leilao_unico(page, args.url)
            else:
                # Comportamento padrão: extrair tudo (compatibilidade)
                print("Modo padrão: Extraindo todos os leilões...")
                dados = extrair_todos_os_leiloes(page)
                if dados:
                    with open('leiloes_completo.json', 'w', encoding='utf-8') as f:
                        json.dump(dados, f, ensure_ascii=False, indent=2)
            
        except KeyboardInterrupt:
            print("\n\n⚠ Execução interrompida pelo usuário (Ctrl+C)")
        except Exception as e:
            print(f"\n✗ Erro fatal: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
        finally:
            print("\nFechando navegador...")
            browser.close()
            print("✓ Navegador fechado\n")


if __name__ == "__main__":
    main()
