from playwright.sync_api import sync_playwright
from .base import BaseRPAProvider
from typing import Dict, Any, List
import time
import random
import os
import subprocess
import re

def human_sleep(min_sec=0.2, max_sec=1.0):
    time.sleep(random.uniform(min_sec, max_sec))

def launch_real_browser(url: str = None):
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    ]
    exe = next((p for p in paths if os.path.exists(p)), None)
    if not exe:
        raise Exception("Navegador nao encontrado (Chrome ou Edge)")
    profile_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "chrome_rpa_profile"))
    
    cmd = [exe, "--remote-debugging-port=9222", f"--user-data-dir={profile_dir}"]
    if url:
        cmd.append(url)
        
    subprocess.Popen(cmd)
    time.sleep(4)

class SiteConsignet(BaseRPAProvider):
    @property
    def name(self) -> str:
        return "site_consignet"

    @property
    def display_name(self) -> str:
        return "Consignet (Login Manual)"

    @property
    def required_configs(self) -> List[Dict[str, Any]]:
        return [
            {"key": "convenio", "label": "Convênio (Nome ou Código)", "type": "text"},
            {"key": "tipo_dado", "label": "Dado de Entrada", "type": "select", "options": [
                {"value": "cpf", "label": "CPF"},
                {"value": "matricula", "label": "Matrícula"}
            ]}
        ]

    def execute(self, items: List[str], config: Dict[str, Any], progress_callback=None, get_speed_callback=None, check_rate_limit_callback=None, register_query_callback=None, partial_save_callback=None) -> List[Dict[str, Any]]:
        results = []
        convenio = config.get("convenio", "")
        tipo_dado = config.get("tipo_dado", "cpf").lower().strip()

        if progress_callback:
            progress_callback(0, len(items), "Abrindo navegador real do Windows...")

        # Inicia o navegador SEM forcar uma aba de login inicialmente
        launch_real_browser()

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
            context = browser.contexts[0]

            logged_in = False
            page = None

            # 1. Procura abas ja existentes que estejam logadas
            for pg in context.pages:
                if re.search(r".*(/auth/context|/admin/).*", pg.url):
                    page = pg
                    logged_in = True
                    break

            # 2. Se nao achou uma aba logada, tenta abrir o context pra ver se a sessao ta viva
            if not logged_in:
                if progress_callback:
                    progress_callback(0, len(items), "Verificando sessao...", "aguardando_login")
                
                page = next((pg for pg in context.pages if pg.url == "about:blank"), None)
                if not page:
                    page = context.new_page()
                
                page.goto("https://www.www1.consignet.com.br/auth/context")
                try:
                    page.wait_for_url(re.compile(r".*(/auth/login|/auth/context|/admin/).*"), timeout=5000)
                except Exception:
                    pass
                
                if re.search(r".*(/auth/context|/admin/).*", page.url):
                    logged_in = True

            # 3. Se realmente nao ta logado, aguarda login manual
            if not logged_in:
                if progress_callback:
                    progress_callback(0, len(items), "Aguardando voce logar manualmente...", "aguardando_login")

                while not logged_in:
                    if get_speed_callback:
                        get_speed_callback()
                    try:
                        for pg in context.pages:
                            if re.search(r".*(/auth/context|/admin/).*", pg.url):
                                page = pg
                                logged_in = True
                                break
                    except Exception:
                        pass
                    if logged_in:
                        break
                    time.sleep(1)

            try:
                page.bring_to_front()
            except Exception:
                pass

            if progress_callback:
                progress_callback(0, len(items), "Login detectado! Navegando...", "running_rpa")

            # 2. Navegacao Inicial
            human_sleep(0.5, 1.0)

            if convenio:
                if progress_callback:
                    progress_callback(0, len(items), f"Selecionando convênio: {convenio}...", "running_rpa")
                
                try:
                    page.goto("https://www.www1.consignet.com.br/auth/context")
                    page.wait_for_selector("input#context-search", state="visible", timeout=10000)
                    page.fill("input#context-search", "")
                    page.type("input#context-search", convenio, delay=random.randint(20, 50))
                    human_sleep(0.2, 0.5)
                    page.press("input#context-search", "Enter")
                    human_sleep(1.0, 1.5)
                    
                    try:
                        # Clica no primeiro item de convenio que aparecer na busca
                        page.click(".context-item", delay=random.randint(20, 50), timeout=5000)
                        page.wait_for_url("**/admin/home", timeout=15000)
                    except Exception:
                        pass
                except Exception as e:
                    print(f"Falha ao tentar selecionar o convenio '{convenio}' (pode estar vazio ou erro): {e}")

            human_sleep(0.5, 1.0)
            page.goto("https://www.www1.consignet.com.br/admin/margem-contratacao")
            page.wait_for_url("**/admin/margem-contratacao", timeout=60000)
            human_sleep(0.5, 1.0)

            # 3. Inicia o loop de coletas
            ultimo_cpf_coletado = None
            try:
                for i, item in enumerate(items):

                    # CHECAGEM DE LIMITE DE CONSULTAS (RATE LIMIT)
                    if check_rate_limit_callback:
                        wait_sec = check_rate_limit_callback()
                        if wait_sec > 0:
                            if progress_callback:
                                progress_callback(i, len(items), "Limite atingido. Pausa de %d min..." % int(wait_sec / 60), "aguardando_limite")
                            while wait_sec > 0:
                                sleep_time = min(5, wait_sec)
                                time.sleep(sleep_time)
                                
                                if get_speed_callback:
                                    get_speed_callback()  # aborta se cancelado
                                    
                                # Re-avalia o limite a cada 5s (caso o usuario mude nas configs)
                                new_wait_sec = check_rate_limit_callback()
                                if new_wait_sec <= 0:
                                    break
                                wait_sec = new_wait_sec
                                
                            try:
                                page.goto("https://www.www1.consignet.com.br/admin/margem-contratacao")
                                page.wait_for_url("**/admin/margem-contratacao", timeout=10000)
                            except Exception:
                                pass

                    # CHECAGEM DE VELOCIDADE EM TEMPO REAL
                    s_mult = get_speed_callback() if get_speed_callback else 1.0

                    # Verifica se a sessao expirou
                    if "/auth/login" in page.url or "margem-contratacao" not in page.url:
                        if progress_callback:
                            progress_callback(i, len(items), "Sessao expirada! Logue no navegador para continuar.", "aguardando_login")

                        try:
                            page.evaluate("""
                                const div = document.createElement('div');
                                div.style.cssText = 'position:fixed;top:0;left:0;width:100%;background:red;color:white;text-align:center;z-index:999999;font-size:24px;padding:20px;font-weight:bold;';
                                div.innerHTML = 'A SESSAO EXPIROU! POR FAVOR, FACA O LOGIN NOVAMENTE PARA O ROBO CONTINUAR.';
                                document.body.prepend(div);
                            """)
                        except Exception:
                            pass

                        logged_in2 = False
                        while not logged_in2:
                            if get_speed_callback:
                                get_speed_callback()
                            try:
                                if len(context.pages) == 0:
                                    pg = context.new_page()
                                    pg.goto("https://www.www1.consignet.com.br/admin/home")
                                for pg in context.pages:
                                    if re.search(r".*(/auth/context|/admin/home).*", pg.url):
                                        page = pg
                                        logged_in2 = True
                                        break
                            except Exception:
                                pass
                            if logged_in2:
                                break
                            time.sleep(1)

                        try:
                            page.bring_to_front()
                        except Exception:
                            pass

                        if progress_callback:
                            progress_callback(i, len(items), "Retomando automacao...", "running_rpa")

                        page.goto("https://www.www1.consignet.com.br/admin/margem-contratacao")
                        page.wait_for_url("**/admin/margem-contratacao", timeout=60000)

                    if progress_callback:
                        progress_callback(i, len(items), "Consultando %s..." % item)

                    # Passo 1: Preencher o campo de busca
                    if tipo_dado == "matricula":
                        page.click("input#search-funcionario-matricula")
                        page.fill("input#search-funcionario-matricula", "")
                        human_sleep(0.1 * s_mult, 0.3 * s_mult)
                        page.type("input#search-funcionario-matricula", str(item), delay=int(random.randint(15, 40) * s_mult))
                        human_sleep(0.2 * s_mult, 0.4 * s_mult)
                        
                        # Limpa CPF cacheado para não ler lixo na validação
                        try:
                            page.evaluate('document.querySelector("input#search-funcionario-cpf").value = ""')
                        except: pass
                        
                        page.press("input#search-funcionario-matricula", "Enter")
                    else:
                        page.click("input#search-funcionario-cpf")
                        page.fill("input#search-funcionario-cpf", "")
                        human_sleep(0.1 * s_mult, 0.3 * s_mult)
                        page.type("input#search-funcionario-cpf", str(item), delay=int(random.randint(15, 40) * s_mult))
                        human_sleep(0.2 * s_mult, 0.4 * s_mult)
                        page.press("input#search-funcionario-cpf", "Enter")

                    if register_query_callback:
                        register_query_callback()

                    # Tempo minimo para o servidor responder a busca inicial
                    min_sleep = max(0.5, 0.7 * s_mult)
                    human_sleep(min_sleep, min_sleep + 0.5)

                    # Passo 2: Coletar o CPF real e a margem
                    cpf_input = page.locator("input#search-funcionario-cpf")
                    
                    # Aguarda o CPF ser preenchido e desocultado validando os numeros
                    cpf_coletado = ""
                    for attempt in range(10): # Tenta por aprox. 4 a 5 segundos
                        if cpf_input.is_visible():
                            val = cpf_input.input_value()
                            if val:
                                val_limpo = val.replace(".", "").replace("-", "").strip()
                                
                                # Se é numérico e tem 11 digitos, sucesso!
                                if val_limpo.isdigit() and len(val_limpo) == 11:
                                    # NOVA CHECAGEM: É exatamente o mesmo CPF de 1 segundo atrás?
                                    if val == ultimo_cpf_coletado and attempt < 4:
                                        # Pode ser um "fantasma" do cache que o JS não limpou a tempo.
                                        # Vamos ignorar essa rodada para dar chance do site atualizar.
                                        pass
                                    else:
                                        cpf_coletado = val
                                        break
                                
                                # Se chegou aqui, ou tem asteriscos, letras ou está incompleto
                                try:
                                    toggle_btn = page.locator('button[aria-label="Toggle cpf visibility"]:visible, button:has(svg[data-testid="VisibilityIcon"]):visible').first
                                    if toggle_btn.is_visible(timeout=500):
                                        toggle_btn.click(delay=int(random.randint(10, 30) * s_mult))
                                except Exception:
                                    pass
                        
                        time.sleep(0.5 * s_mult)
                    
                    # Ultima tentativa (garantia de capturar o que ficou na tela)
                    if not cpf_coletado and cpf_input.is_visible():
                        cpf_coletado = cpf_input.input_value()

                    if not cpf_coletado or cpf_coletado.strip() == "":
                        results.append({
                            "cpf": str(item),
                            "cpf_real_coletado": "Nao encontrado",
                            "margem_calculada": "Nao encontrada"
                        })
                    else:
                        margem_coletada = "Falha na consulta"
                        btn_calc = page.locator("button#margem-funcionario-calcular-margem")
                        alerta = page.locator("div.MuiSnackbarContent-message", has_text=re.compile(r"Margem indispon.vel", re.IGNORECASE))
                        margem_loc = page.locator('xpath=//h6[text()="Menor margem calculada"]/following-sibling::h4')
                        
                        found_calc = False
                        msg_alerta = ""
                        
                        # Polling super rapido (ate ~4.5s) esperando o alerta ou o botao aparecer
                        for _ in range(30):
                            if alerta.is_visible():
                                msg_alerta = alerta.inner_text().strip()
                                break
                            if btn_calc.is_visible():
                                found_calc = True
                                break
                            time.sleep(0.15)
                            
                        if msg_alerta:
                            # Se a notificacao apareceu, pegamos o texto e fechamos ela para nao atrapalhar
                            margem_coletada = msg_alerta
                            try:
                                page.click("button#snackbar-btn-close", timeout=1000)
                            except Exception:
                                pass
                        elif found_calc:
                            # Tenta clicar no botao ate 3 vezes
                            for attempt in range(3):
                                try:
                                    btn_calc.click(delay=int(random.randint(20, 50) * s_mult), timeout=2000)
                                    margem_loc.wait_for(state="visible", timeout=4000)
                                    margem_coletada = margem_loc.inner_text()
                                    break
                                except Exception:
                                    time.sleep(0.5)

                        results.append({
                            "cpf": str(item),
                            "cpf_real_coletado": cpf_coletado,
                            "margem_calculada": margem_coletada
                        })

                    # Salvar o progresso no CSV a cada iteracao para recuperacao de desastres
                    if partial_save_callback:
                        try:
                            partial_save_callback(results)
                        except Exception as p_e:
                            print(f"Erro no salvamento parcial: {p_e}")

                    # Passo 3: Limpar a tela para o proximo item
                    human_sleep(0.2 * s_mult, 0.5 * s_mult)
                    voltar_btn = page.locator("button#icon-btn-voltar-pagina")
                    close_btn = page.locator('button[aria-label="Apagar informacoes do colaborador"]')

                    try:
                        voltar_btn.wait_for(state="visible", timeout=1500)
                        voltar_btn.click(delay=int(random.randint(20, 50) * s_mult))
                    except Exception:
                        try:
                            close_btn.first.wait_for(state="visible", timeout=1500)
                            close_btn.first.click(delay=int(random.randint(20, 50) * s_mult))
                        except Exception:
                            try:
                                generic_x = page.locator('button:has(svg[data-testid="CloseIcon"]):visible').first
                                generic_x.wait_for(timeout=1500)
                                generic_x.click(delay=int(random.randint(20, 50) * s_mult))
                            except Exception:
                                # Se os botoes realmente nao aparecerem, recarrega a pagina
                                page.goto("https://www.www1.consignet.com.br/admin/margem-contratacao")
                                try:
                                    page.wait_for_url("**/admin/margem-contratacao", timeout=10000)
                                except Exception:
                                    pass

                    # Guarda o CPF coletado nesta rodada para checagem de cache na próxima
                    ultimo_cpf_coletado = cpf_coletado
                    
                    # Pausa leve antes do proximo CPF
                    human_sleep(0.3 * s_mult, 0.8 * s_mult)

                if progress_callback:
                    progress_callback(len(items), len(items), "Finalizado!", "completed")

            except Exception as e:
                import traceback
                print("Erro Critico no loop do robo: %s" % traceback.format_exc())
                if progress_callback:
                    progress_callback(len(results), len(items), "Parada brusca: %s" % str(e), "error")
            finally:
                browser.close()

        return results
