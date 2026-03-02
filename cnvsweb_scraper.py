import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urlparse, parse_qs
import json

class CNVSWebScraper:
    def __init__(self, token):
        self.base_url = "https://cnvsweb.stream"
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://cnvsweb.stream/',
        })
        self.last_activity = time.time()
        self.logged_in = False
        # OTIMIZAÇÃO: Timeout para evitar travamento
        self.timeout = 15
    
    def login(self):
        """Faz login no site usando o token"""
        try:
            login_page_url = f"{self.base_url}/login"
            login_ajax_url = f"{self.base_url}/ajax/login.php"
            
            # Primeiro GET para pegar cookies
            print("🔑 Acessando página de login...")
            response = self.session.get(login_page_url, timeout=self.timeout)
            time.sleep(0.5)  # OTIMIZAÇÃO: Reduzido de 1s
            
            # POST para o endpoint AJAX com o token
            payload = {
                'uid': None,
                'email': None,
                'token': self.token,
                'emailVerified': None,
                'displayName': None,
                'photoURL': None,
                'phoneNumber': None,
                'referer': ''
            }
            
            # Headers específicos para o AJAX
            ajax_headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Origin': self.base_url,
                'Referer': login_page_url
            }
            
            print(f"🔑 Fazendo login com token: {self.token}")
            response = self.session.post(
                login_ajax_url, 
                data=payload, 
                headers=ajax_headers,
                allow_redirects=False,
                timeout=self.timeout  # OTIMIZAÇÃO
            )
            
            print(f"📊 Status do login: {response.status_code}")
            
            # Verifica a resposta JSON
            if response.status_code == 200:
                try:
                    data = response.json()
                    print(f"📦 Resposta JSON: {data}")
                    
                    if data.get('status') == 'success':
                        redirect_url = data.get('redirect', self.base_url)
                        print(f"✓ Login realizado com sucesso!")
                        print(f"↪️  Redirecionando para: {redirect_url}")
                        
                        # Acessa a página de redirecionamento para completar o login
                        response = self.session.get(redirect_url, timeout=self.timeout)
                        
                        # Verifica se está realmente logado
                        if response.status_code == 200 and '/login' not in response.url:
                            print("✓ Login confirmado - sessão ativa")
                            self.last_activity = time.time()
                            self.logged_in = True
                            return True
                        else:
                            print(f"⚠ Redirecionamento falhou")
                            return False
                    else:
                        error_msg = data.get('message', 'Erro desconhecido')
                        print(f"✗ Erro no login: {error_msg}")
                        return False
                        
                except ValueError as e:
                    print(f"✗ Resposta não é JSON válido: {response.text[:200]}")
                    return False
            else:
                print(f"✗ Erro no login: Status {response.status_code}")
                print(f"📝 Resposta: {response.text[:200]}")
                return False
                
        except Exception as e:
            print(f"✗ Erro no login: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def keep_alive(self):
        """Atualiza a sessão para não deslogar"""
        if not self.logged_in:
            return
            
        current_time = time.time()
        # Verifica se passaram 3 minutos desde a última atividade
        if current_time - self.last_activity > 180:  # 3 minutos
            print("⟳ Atualizando sessão...")
            try:
                response = self.session.get(self.base_url, timeout=self.timeout)
                self.last_activity = time.time()
                print("✓ Sessão atualizada")
            except Exception as e:
                print(f"Erro ao atualizar sessão: {e}")
    
    def get_most_watched_today(self, get_video_urls=True, max_episodes_per_series=5, organize_output=True):
        """
        Pega os filmes/séries mais assistidos do dia
        
        Args:
            get_video_urls: Se True, extrai URLs dos vídeos
            max_episodes_per_series: Máximo de episódios para extrair por série (0 = todos)
            organize_output: Se True, retorna dados organizados em {movies: [], series: []}
        """
        self.keep_alive()
        
        try:
            print("📡 Acessando página principal...")
            response = self.session.get(self.base_url)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procura pela seção "Mais Visto do Dia"
            most_watched_section = None
            
            # MÉTODO 1: Procura por h5 com texto exato
            all_h5 = soup.find_all('h5')
            for h5 in all_h5:
                if h5.text and 'Mais Visto' in h5.text:
                    most_watched_section = h5
                    print(f"✓ Seção encontrada: '{h5.text.strip()}'")
                    break
            
            if not most_watched_section:
                print("✗ Seção 'Mais Visto do Dia' não encontrada")
                print(f"🔍 Seções encontradas: {[h5.text.strip() for h5 in all_h5]}")
                return []
            
            # Pega o container pai
            container = most_watched_section.find_parent('div', class_='col-12')
            
            if not container:
                print("✗ Container pai não encontrado")
                return []
            
            print("✓ Container encontrado")
            
            movies = []
            # Procura por todos os slides
            items = container.find_all('div', class_='swiper-slide')
            
            if not items:
                # Método alternativo
                items = container.find_all('div', class_='item')
            
            print(f"📊 Encontrados {len(items)} itens na seção")
            
            for idx, item in enumerate(items, 1):
                try:
                    # Extrai informações do item
                    info_div = item.find('div', class_='info')
                    
                    if not info_div:
                        continue
                    
                    # Título
                    title_tag = info_div.find('h6')
                    title = title_tag.text.strip() if title_tag else "Sem título"
                    
                    # Link para assistir
                    watch_btn = info_div.find('a', href=True)
                    watch_link = watch_btn['href'] if watch_btn else ""
                    
                    # Tags (duração/temporadas, ano, IMDb)
                    tags = info_div.find('p', class_='tags')
                    duration_or_seasons = ""
                    year = ""
                    imdb = ""
                    
                    if tags:
                        spans = tags.find_all('span')
                        if len(spans) > 0:
                            duration_or_seasons = spans[0].text.strip()
                        if len(spans) > 1:
                            year = spans[1].text.strip()
                        if len(spans) > 2:
                            imdb_text = spans[2].text.strip()
                            # Remove "IMDb" do texto
                            imdb = imdb_text.replace('IMDb', '').strip()
                    
                    # Imagem de fundo
                    content_div = item.find('div', class_='content')
                    image_url = ""
                    if content_div:
                        bg_style = content_div.get('style', '')
                        image_match = re.search(r'url\((.*?)\)', bg_style)
                        if image_match:
                            image_url = image_match.group(1).strip('"\'')
                    
                    # Detecta se é série ou filme
                    is_series = 'Temporada' in duration_or_seasons
                    
                    movie_data = {
                        'title': title,
                        'type': 'series' if is_series else 'movie',  # NOVO: identifica o tipo
                        'watch_link': watch_link,
                        'duration_or_seasons': duration_or_seasons,
                        'year': year,
                        'imdb': imdb,
                        'image_url': image_url,
                        'player_url': None,
                        'video_url': None,
                        'is_series': is_series,
                        'episodes': []
                    }
                    
                    print(f"  {idx}. {title}")
                    
                    # Se solicitado, extrai URLs do player e vídeo
                    if get_video_urls and watch_link:
                        if is_series:
                            print(f"     📺 Série detectada - extraindo episódios...")
                            try:
                                episodes = self.get_series_episodes(watch_link)
                                
                                # NOVO: Limita número de episódios se configurado
                                if max_episodes_per_series > 0:
                                    episodes = episodes[:max_episodes_per_series]
                                    print(f"     ⚠ Limitado a {max_episodes_per_series} episódios")
                                
                                movie_data['episodes'] = episodes
                                
                                # Opcionalmente, extrai URLs de vídeo dos episódios
                                if episodes:
                                    print(f"     🎬 Extraindo URLs de vídeo dos episódios...")
                                    for ep in episodes[:10000000]:  # Primeiros 10000000 episódios como exemplo
                                        if ep.get('player_url'):
                                            try:
                                                video_url = self.get_video_mp4_url(ep['player_url'])
                                                ep['video_url'] = video_url
                                                if video_url:
                                                    print(f"        ✓ {ep['title']}: {video_url[:60]}...")
                                            except Exception as e:
                                                print(f"        ✗ Erro: {e}")
                            except Exception as e:
                                print(f"     ✗ Erro ao extrair episódios: {e}")
                        else:
                            print(f"     🎬 Filme detectado - extraindo vídeo...")
                            try:
                                player_url = self.get_player_url(watch_link)
                                movie_data['player_url'] = player_url
                                
                                if player_url:
                                    print(f"     ✓ Player: {player_url[:60]}...")
                                    video_url = self.get_video_mp4_url(player_url)
                                    movie_data['video_url'] = video_url
                                    if video_url:
                                        print(f"     ✓ Vídeo: {video_url[:80]}...")
                                    else:
                                        print(f"     ⚠ URL do vídeo não encontrada")
                                else:
                                    print(f"     ⚠ URL do player não encontrada")
                            except Exception as e:
                                print(f"     ✗ Erro ao extrair vídeo: {e}")
                    
                    movies.append(movie_data)
                    
                    # Delay para não sobrecarregar o servidor
                    if get_video_urls and idx < len(items):
                        time.sleep(0.3)
                    
                except Exception as e:
                    print(f"  ✗ Erro ao processar item {idx}: {e}")
                    continue
            
            print(f"\n✓ Total: {len(movies)} filmes extraídos")
            
            # NOVO: Retorna dados organizados se solicitado
            if organize_output:
                organized_data = {
                    'movies': [m for m in movies if m['type'] == 'movie'],
                    'series': [m for m in movies if m['type'] == 'series'],
                    'summary': {
                        'total': len(movies),
                        'movies': len([m for m in movies if m['type'] == 'movie']),
                        'series': len([m for m in movies if m['type'] == 'series'])
                    }
                }
                print(f"📊 Organizado: {organized_data['summary']['movies']} filmes, {organized_data['summary']['series']} séries")
                return organized_data
            
            return movies
            
        except Exception as e:
            print(f"✗ Erro ao buscar filmes mais assistidos: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def search_movies(self, query, get_video_urls=True, max_episodes_per_series=5, organize_output=True):
        """
        Busca filmes/séries no site
        
        Args:
            query: Termo de busca
            get_video_urls: Se True, extrai URLs dos vídeos
            max_episodes_per_series: Máximo de episódios para extrair por série (0 = todos)
            organize_output: Se True, retorna dados organizados em {movies: [], series: []}
        """
        self.keep_alive()
        
        try:
            search_url = f"{self.base_url}/search.php"
            params = {'q': query}
            
            print(f"🔍 Buscando: {query}")
            response = self.session.get(search_url, params=params)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            movies = []
            items = soup.find_all('div', class_='item poster')
            
            print(f"📊 Encontrados {len(items)} resultados")
            
            for idx, item in enumerate(items, 1):
                try:
                    info_div = item.find('div', class_='info')
                    if not info_div:
                        continue
                    
                    title_tag = info_div.find('h6')
                    title = title_tag.text.strip() if title_tag else "Sem título"
                    
                    watch_btn = info_div.find('a', href=True)
                    watch_link = watch_btn['href'] if watch_btn else ""
                    
                    tags = info_div.find('p', class_='tags')
                    duration_or_seasons = ""
                    year = ""
                    imdb = ""
                    
                    if tags:
                        spans = tags.find_all('span')
                        if len(spans) > 0:
                            duration_or_seasons = spans[0].text.strip()
                        if len(spans) > 1:
                            year = spans[1].text.strip()
                        if len(spans) > 2:
                            imdb_text = spans[2].text.strip()
                            imdb = imdb_text.replace('IMDb', '').strip()
                    
                    content_div = item.find('div', class_='content')
                    image_url = ""
                    if content_div:
                        bg_style = content_div.get('style', '')
                        image_match = re.search(r'url\((.*?)\)', bg_style)
                        if image_match:
                            image_url = image_match.group(1).strip('"\'')
                    
                    movie_data = {
                        'title': title,
                        'type': 'series' if 'Temporada' in duration_or_seasons else 'movie',  # NOVO
                        'watch_link': watch_link,
                        'duration_or_seasons': duration_or_seasons,
                        'year': year,
                        'imdb': imdb,
                        'image_url': image_url,
                        'player_url': None,
                        'video_url': None,
                        'is_series': 'Temporada' in duration_or_seasons,
                        'episodes': []
                    }
                    
                    print(f"  {idx}. {title}")
                    
                    # Detecta se é série ou filme
                    is_series = 'Temporada' in duration_or_seasons
                    
                    if get_video_urls and watch_link:
                        if is_series:
                            print(f"     📺 Série detectada - extraindo episódios...")
                            try:
                                episodes = self.get_series_episodes(watch_link)
                                
                                # NOVO: Limita número de episódios se configurado
                                if max_episodes_per_series > 0:
                                    episodes = episodes[:max_episodes_per_series]
                                    print(f"     ⚠ Limitado a {max_episodes_per_series} episódios")
                                
                                movie_data['episodes'] = episodes
                                
                                # Opcionalmente, extrai URLs de vídeo dos primeiros episódios
                                if episodes:
                                    print(f"     🎬 Extraindo URLs de vídeo dos primeiros episódios...")
                                    for ep in episodes[:3]:  # Primeiros 3 como exemplo
                                        if ep.get('player_url'):
                                            try:
                                                video_url = self.get_video_mp4_url(ep['player_url'])
                                                ep['video_url'] = video_url
                                                if video_url:
                                                    print(f"        ✓ {ep['title']}: {video_url[:60]}...")
                                            except Exception as e:
                                                print(f"        ✗ Erro: {e}")
                            except Exception as e:
                                print(f"     ✗ Erro ao extrair episódios: {e}")
                        else:
                            print(f"     🎬 Filme detectado - extraindo vídeo...")
                            try:
                                player_url = self.get_player_url(watch_link)
                                movie_data['player_url'] = player_url
                                
                                if player_url:
                                    print(f"     ✓ Player: {player_url[:60]}...")
                                    video_url = self.get_video_mp4_url(player_url)
                                    movie_data['video_url'] = video_url
                                    if video_url:
                                        print(f"     ✓ Vídeo: {video_url[:80]}...")
                                    else:
                                        print(f"     ⚠ Vídeo não encontrado")
                                else:
                                    print(f"     ⚠ Player não encontrado")
                            except Exception as e:
                                print(f"     ✗ Erro: {e}")
                    
                    movies.append(movie_data)
                    
                    if get_video_urls and idx < len(items):
                        time.sleep(0.3)
                    
                except Exception as e:
                    print(f"  ✗ Erro ao processar item {idx}: {e}")
                    continue
            
            print(f"\n✓ Total: {len(movies)} resultados para '{query}'")
            
            # NOVO: Retorna dados organizados se solicitado
            if organize_output:
                organized_data = {
                    'movies': [m for m in movies if m['type'] == 'movie'],
                    'series': [m for m in movies if m['type'] == 'series'],
                    'summary': {
                        'total': len(movies),
                        'movies': len([m for m in movies if m['type'] == 'movie']),
                        'series': len([m for m in movies if m['type'] == 'series'])
                    }
                }
                print(f"📊 Organizado: {organized_data['summary']['movies']} filmes, {organized_data['summary']['series']} séries")
                return organized_data
            
            return movies
            
        except Exception as e:
            print(f"✗ Erro na busca: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_movie_details(self, movie_url):
        """Extrai TODAS as informações detalhadas de um filme"""
        self.keep_alive()
        
        try:
            if not movie_url.startswith('http'):
                movie_url = urljoin(self.base_url, movie_url)
            
            print(f"📄 Acessando página do filme: {movie_url}")
            response = self.session.get(movie_url)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            movie_info = {
                'title': '',
                'original_title': '',
                'year': '',
                'duration': '',
                'genres': [],
                'imdb_rating': '',
                'synopsis': '',
                'director': '',
                'cast': [],
                'trailer_url': '',
                'image_url': '',
                'backdrop_url': '',
                'watch_link': movie_url,
                'player_url': None,
                'video_url': None
            }
            
            # Título
            title_tag = soup.find('h1') or soup.find('h2', class_='title')
            if title_tag:
                movie_info['title'] = title_tag.text.strip()
            
            # Imagem principal
            poster_div = soup.find('div', class_='poster') or soup.find('img', class_='poster')
            if poster_div:
                if poster_div.name == 'img':
                    movie_info['image_url'] = poster_div.get('src', '')
                else:
                    bg_style = poster_div.get('style', '')
                    image_match = re.search(r'url\((.*?)\)', bg_style)
                    if image_match:
                        movie_info['image_url'] = image_match.group(1).strip('"\'')
            
            # Sinopse
            synopsis_div = soup.find('div', class_='synopsis') or soup.find('p', class_='overview')
            if synopsis_div:
                movie_info['synopsis'] = synopsis_div.text.strip()
            
            # Tags (ano, duração, IMDb)
            tags = soup.find('p', class_='tags') or soup.find('div', class_='tags')
            if tags:
                spans = tags.find_all('span')
                for span in spans:
                    text = span.text.strip()
                    if 'Min' in text or 'Temporadas' in text:
                        movie_info['duration'] = text
                    elif text.isdigit() and len(text) == 4:
                        movie_info['year'] = text
                    elif 'IMDb' in text:
                        movie_info['imdb_rating'] = text.replace('IMDb', '').strip()
            
            # Gêneros
            genres_div = soup.find('div', class_='genres')
            if genres_div:
                genre_links = genres_div.find_all('a')
                movie_info['genres'] = [g.text.strip() for g in genre_links]
            
            # Player e vídeo
            print("     🎬 Extraindo player e vídeo...")
            player_url = self.get_player_url(movie_url)
            movie_info['player_url'] = player_url
            
            if player_url:
                print(f"     ✓ Player: {player_url}")
                video_url = self.get_video_mp4_url(player_url)
                movie_info['video_url'] = video_url
                if video_url:
                    print(f"     ✓ Vídeo MP4 extraído")
            
            return movie_info
            
        except Exception as e:
            print(f"✗ Erro ao obter detalhes do filme: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_player_url(self, movie_url, save_debug_html=False):
        """Extrai a URL do player do filme"""
        self.keep_alive()
        
        try:
            if not movie_url.startswith('http'):
                movie_url = urljoin(self.base_url, movie_url)
            
            print(f"       🌐 Acessando: {movie_url}")
            response = self.session.get(movie_url)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Opção de salvar HTML para debug
            if save_debug_html:
                filename = f"debug_{movie_url.split('/')[-1]}.html"
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(soup.prettify())
                print(f"       💾 HTML salvo em: {filename}")
            
            # DEBUG: Mostra todos os botões/links encontrados
            all_buttons = soup.find_all('a', class_=lambda x: x and 'btn' in str(x))
            print(f"       📊 Encontrados {len(all_buttons)} botões na página")
            
            for i, btn in enumerate(all_buttons[:5], 1):  # Primeiros 5
                text = btn.get_text(strip=True)[:30]
                href = btn.get('href', 'N/A')
                classes = btn.get('class', [])
                print(f"       🔘 Botão {i}: '{text}' | href='{href}' | class={classes}")
            
            # MÉTODO 1: Procura botão "ASSISTIR" - várias tentativas
            assistir_btn = None
            
            # Tentativa 1: classe "btn free"
            assistir_btn = soup.find('a', class_='btn free')
            if assistir_btn:
                print(f"       ✓ Encontrado com classe 'btn free'")
            
            # Tentativa 2: classe contendo "btn" e texto "ASSISTIR"
            if not assistir_btn:
                all_links = soup.find_all('a')
                for link in all_links:
                    text = link.get_text(strip=True).upper()
                    if 'ASSISTIR' in text or 'PLAY' in text:
                        assistir_btn = link
                        print(f"       ✓ Encontrado por texto: '{link.get_text(strip=True)}'")
                        break
            
            # Tentativa 3: procura por data-tippy-content com "Assistir"
            if not assistir_btn:
                assistir_btn = soup.find('a', attrs={'data-tippy-content': lambda x: x and 'Assistir' in x})
                if assistir_btn:
                    print(f"       ✓ Encontrado por data-tippy-content")
            
            if assistir_btn:
                href = assistir_btn.get('href', '')
                print(f"       🎯 Botão ASSISTIR encontrado com href: '{href}'")
                
                # CASO 1: Se o href é uma URL completa (http://...), é o player direto!
                if href.startswith('http'):
                    if 'play' in href.lower() or 'stream' in href.lower():
                        print(f"       ✓ URL do player encontrada diretamente!")
                        return href
                    else:
                        print(f"       ⚠ URL não parece ser um player: {href}")
                
                # CASO 2: Se o href começa com #, é uma âncora para um elemento na mesma página
                elif href.startswith('#'):
                    element_id = href[1:]  # Remove o #
                    print(f"       🔍 Procurando elemento com ID: '{element_id}'")
                    
                    # Procura o elemento com esse ID
                    player_element = soup.find(id=element_id)
                    
                    if player_element:
                        print(f"       ✓ Elemento encontrado: {element_id}")
                        print(f"       📝 Tag: {player_element.name}, Classes: {player_element.get('class', [])}")
                        
                        # Procura por iframe dentro desse elemento
                        iframe = player_element.find('iframe')
                        
                        if iframe:
                            src = iframe.get('src', '')
                            if src:
                                player_url = src if src.startswith('http') else urljoin(self.base_url, src)
                                print(f"       ✓ iframe encontrado: {player_url[:80]}...")
                                return player_url
                            else:
                                print(f"       ⚠ iframe sem src")
                        else:
                            print(f"       ⚠ Nenhum iframe dentro do elemento {element_id}")
                            
                            # Debug: mostra o conteúdo do elemento
                            print(f"       📝 Conteúdo do elemento (primeiros 200 chars):")
                            print(f"           {str(player_element)[:200]}")
                        
                        # Se não encontrou iframe, procura por data-src ou data-player
                        for attr in ['data-src', 'data-player', 'data-url', 'data-iframe']:
                            elem_with_attr = player_element.find(attrs={attr: True})
                            if elem_with_attr:
                                data_src = elem_with_attr.get(attr)
                                if data_src:
                                    player_url = data_src if data_src.startswith('http') else urljoin(self.base_url, data_src)
                                    print(f"       ✓ URL encontrada em {attr}: {player_url[:80]}...")
                                    return player_url
                    else:
                        print(f"       ⚠ Elemento com ID '{element_id}' não encontrado")
                        
                        # Debug: lista todos os IDs disponíveis
                        all_ids = [elem.get('id') for elem in soup.find_all(id=True)]
                        print(f"       📝 IDs disponíveis na página: {all_ids[:10]}")
                
                # CASO 3: Se for URL relativa, converte para absoluta
                elif href.startswith('/'):
                    full_url = urljoin(self.base_url, href)
                    print(f"       ✓ URL relativa convertida: {full_url}")
                    return full_url
                else:
                    print(f"       ⚠ Formato de href não reconhecido: '{href}'")
            else:
                print(f"       ⚠ Botão ASSISTIR não encontrado")
            
            # MÉTODO 2: Procura por iframes na página com "play" no src
            print(f"       🔍 Procurando iframes na página...")
            iframes = soup.find_all('iframe')
            print(f"       📊 Encontrados {len(iframes)} iframes")
            
            for idx, iframe in enumerate(iframes):
                src = iframe.get('src', '')
                iframe_id = iframe.get('id', 'N/A')
                print(f"       🔍 iframe {idx+1}: id='{iframe_id}' src='{src[:60] if src else 'sem src'}...'")
                
                if src and ('play' in src.lower() or 'stream' in src.lower()):
                    player_url = src if src.startswith('http') else urljoin(self.base_url, src)
                    print(f"       ✓ iframe com 'play' ou 'stream' encontrado")
                    return player_url
            
            # MÉTODO 3: Pega o primeiro iframe disponível
            if iframes and iframes[0].get('src'):
                player_url = iframes[0]['src']
                if not player_url.startswith('http'):
                    player_url = urljoin(self.base_url, player_url)
                print(f"       ⚠ Usando primeiro iframe disponível")
                return player_url
            
            print(f"       ✗ Nenhum player encontrado")
            return None
            
        except Exception as e:
            print(f"       ✗ Erro ao extrair player URL: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_series_episodes(self, watch_link):
        """Extrai todos os episódios de todas as temporadas de uma série"""
        self.keep_alive()
        
        try:
            if not watch_link.startswith('http'):
                watch_link = urljoin(self.base_url, watch_link)
            
            print(f"       📺 Acessando página da série: {watch_link}")
            response = self.session.get(watch_link)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procura o select de temporadas
            seasons_select = soup.find('select', id='seasons-view')
            
            if not seasons_select:
                print(f"       ⚠ Select de temporadas não encontrado")
                return []
            
            # Pega todas as temporadas
            seasons = seasons_select.find_all('option')
            print(f"       📊 Encontradas {len(seasons)} temporadas")
            
            all_episodes = []

            # Itera por TODAS as temporadas fazendo requisição AJAX para cada uma
            for season_option in seasons:
                season_id = season_option.get('value', '')
                season_name = season_option.get_text(strip=True)

                if not season_id:
                    continue

                print(f"       🎬 Buscando episódios da {season_name} (id={season_id})...")

                # Requisição AJAX para carregar episódios da temporada
                ajax_url = f"{self.base_url}/ajax/episodes.php"
                ajax_headers = {
                    'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                    'X-Requested-With': 'XMLHttpRequest',
                    'Accept': 'application/json, text/javascript, */*; q=0.01',
                    'Origin': self.base_url,
                    'Referer': watch_link
                }
                ajax_payload = {'season': season_id}

                try:
                    ajax_response = self.session.post(
                        ajax_url,
                        data=ajax_payload,
                        headers=ajax_headers,
                        timeout=self.timeout
                    )
                    season_soup = BeautifulSoup(ajax_response.content, 'html.parser')
                    episodes_container = season_soup.find('div', id='episodes-view') or season_soup
                    episodes = episodes_container.find_all('div', class_='ep')
                    if not episodes:
                        # Tenta parsear direto o HTML retornado (pode ser fragmento)
                        episodes = season_soup.find_all('div', class_='ep')
                except Exception as e:
                    print(f"       ⚠ Erro ao buscar {season_name} via AJAX: {e}")
                    # Fallback: usa episódios já carregados na página se for temporada selecionada
                    if season_option.get('selected'):
                        episodes_container = soup.find('div', id='episodes-view')
                        episodes = episodes_container.find_all('div', class_='ep') if episodes_container else []
                    else:
                        episodes = []

                print(f"       📊 Encontrados {len(episodes)} episódios na {season_name}")

                for idx, ep in enumerate(episodes, 1):
                    try:
                        # ID do episódio
                        ep_id = ep.get('id', '')
                        
                        # Informações do episódio
                        info_div = ep.find('div', class_='info')
                        
                        if not info_div:
                            continue
                        
                        # Título do episódio
                        title_tag = info_div.find('h5', class_='fw-bold')
                        ep_title = title_tag.get_text(strip=True) if title_tag else f"Episódio {idx}"
                        
                        # Duração
                        duration_tags = info_div.find_all('p', class_='small')
                        duration = "N/A"
                        pub_date = "N/A"
                        
                        for tag in duration_tags:
                            text = tag.get_text(strip=True)
                            if 'Duração:' in text:
                                duration = text.replace('Duração:', '').strip()
                            elif 'Publicado:' in text:
                                pub_date = text.replace('Publicado:', '').strip()
                        
                        # Botão de assistir - procura dentro da div.buttons
                        buttons_div = ep.find('div', class_='buttons')
                        player_url = None
                        
                        if buttons_div:
                            all_links = buttons_div.find_all('a', href=True)
                            for link in all_links:
                                href = link.get('href', '')
                                if href.endswith('>'):
                                    href = href[:-1]
                                if href.startswith('http') and ('playcnvs' in href or 'playmycnvs' in href or '/s/' in href):
                                    player_url = href
                                    break
                            if not player_url:
                                for link in all_links:
                                    href = link.get('href', '')
                                    if href.endswith('>'):
                                        href = href[:-1]
                                    if href.startswith('http') and 'cnvsweb' not in href:
                                        player_url = href
                                        break
                        
                        episode_data = {
                            'episode_id': ep_id,
                            'season': season_name,
                            'season_id': season_id,
                            'title': ep_title,
                            'duration': duration,
                            'published_date': pub_date,
                            'player_url': player_url,
                            'video_url': None
                        }
                        
                        if player_url:
                            print(f"             {idx}. {ep_title}: {player_url[:60]}...")
                        else:
                            print(f"             {idx}. {ep_title}: ⚠ sem player_url")
                        
                        all_episodes.append(episode_data)
                        
                    except Exception as e:
                        print(f"             ✗ Erro ao processar episódio {idx}: {e}")
                        continue
            
            print(f"       ✓ Total de episódios extraídos: {len(all_episodes)}")
            return all_episodes
            
        except Exception as e:
            print(f"       ✗ Erro ao extrair episódios: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    def get_video_mp4_url(self, player_url):
        """Extrai a URL do vídeo .mp4 do player"""
        self.keep_alive()
        
        try:
            print(f"       🔍 Acessando player: {player_url[:60]}...")
            response = self.session.get(player_url)
            self.last_activity = time.time()
            html = response.text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # MÉTODO 1: Procura tag <video> com src
            video_tags = soup.find_all('video')
            print(f"       📊 Encontradas {len(video_tags)} tags <video>")
            
            for idx, video_tag in enumerate(video_tags):
                src = video_tag.get('src')
                if src and '.mp4' in src:
                    print(f"       ✓ URL encontrada em <video> tag #{idx+1}")
                    return src
                
                # Procura <source> dentro de <video>
                source_tags = video_tag.find_all('source')
                for source_tag in source_tags:
                    src = source_tag.get('src')
                    if src:
                        print(f"       ✓ URL encontrada em <source> dentro de <video> #{idx+1}")
                        return src
            
            # MÉTODO 2: Regex mais específico para URLs .mp4 com o padrão do site
            # Padrão: https://server-amz.playmycnvs.com/...mp4?cnvs_token=...
            mp4_patterns = [
                r'https?://server[^"\s]*?\.mp4[^"\s]*',                    # server...mp4
                r'https?://[^"\s]*playmycnvs[^"\s]*?\.mp4[^"\s]*',         # playmycnvs...mp4
                r'src["\s]*[:=]["\s]*([^"\s]+\.mp4[^"\s]*)',               # src="...mp4"
                r'"file"["\s]*:["\s]*"([^"]+\.mp4[^"]*)"',                 # "file":"...mp4"
                r'"src"["\s]*:["\s]*"([^"]+\.mp4[^"]*)"',                  # "src":"...mp4"
                r'https?://[^"\s<>]+\.mp4[^\s<>"\']*',                     # qualquer URL .mp4
            ]
            
            for idx, pattern in enumerate(mp4_patterns):
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    # Pega a primeira URL encontrada
                    video_url = matches[0]
                    
                    # Se for um grupo de captura, usa o grupo
                    if isinstance(video_url, tuple):
                        video_url = video_url[0]
                    
                    # Remove aspas e espaços
                    video_url = video_url.strip('"\'\\').strip()
                    
                    # Verifica se é uma URL válida
                    if video_url.startswith('http') and '.mp4' in video_url:
                        print(f"       ✓ URL encontrada com pattern #{idx+1}: {video_url[:80]}...")
                        return video_url
            
            # MÉTODO 3: Procura por divs com classe específica do player (jw-media, jw-video, etc)
            player_divs = soup.find_all(['div', 'video'], class_=re.compile(r'jw-|player|video', re.I))
            print(f"       📊 Encontrados {len(player_divs)} elementos de player")
            
            for div in player_divs:
                # Procura por data-src ou outros atributos
                for attr in ['data-src', 'data-url', 'data-file', 'src']:
                    url = div.get(attr)
                    if url and '.mp4' in url:
                        print(f"       ✓ URL encontrada em {attr} de elemento player")
                        return url
            
            # MÉTODO 4: Busca agressiva no HTML por qualquer string que pareça uma URL de vídeo
            print(f"       🔍 Fazendo busca agressiva no HTML...")
            all_urls = re.findall(r'https?://[^\s<>"\']+', html)
            
            for url in all_urls:
                url = url.strip('"\'\\,;')
                if '.mp4' in url and ('server' in url.lower() or 'play' in url.lower() or 'cnvs' in url.lower()):
                    print(f"       ✓ URL encontrada em busca agressiva")
                    return url
            
            print(f"       ✗ Nenhuma URL de vídeo encontrada")
            print(f"       📝 Tamanho do HTML: {len(html)} caracteres")
            
            # Debug: salva o HTML para análise
            if len(html) < 10000:  # Só para HTMLs pequenos
                print(f"       📝 HTML snippet: {html[:500]}...")
            
            return None
            
        except Exception as e:
            print(f"       ✗ Erro ao extrair vídeo MP4: {e}")
            import traceback
            traceback.print_exc()
            return None


def main():
    """Função de teste"""
    TOKEN = "2E9RCU0B"
    
    print("\n" + "="*70)
    print("CNVSWeb Scraper - Versão Completa com Organização")
    print("="*70)
    
    scraper = CNVSWebScraper(TOKEN)
    
    # Login
    print("\n" + "="*70)
    print("ETAPA 1: LOGIN")
    print("="*70 + "\n")
    
    if not scraper.login():
        print("\n✗ Falha no login. Verifique o token.")
        return
    
    # Filmes mais assistidos
    print("\n" + "="*70)
    print("ETAPA 2: FILMES MAIS ASSISTIDOS DO DIA")
    print("="*70 + "\n")
    
    # NOVO: Usa organização de dados
    result = scraper.get_most_watched_today(
        get_video_urls=True,
        max_episodes_per_series=3,  # Limita a 3 episódios por série
        organize_output=True  # Retorna organizado
    )
    
    # Verifica se retornou dados organizados ou lista simples
    if isinstance(result, dict) and 'movies' in result:
        # Dados organizados
        most_watched_movies = result['movies']
        most_watched_series = result['series']
        summary = result['summary']
        
        print("\n" + "="*70)
        print(f"RESULTADOS ORGANIZADOS")
        print("="*70)
        print(f"\n📊 Total: {summary['total']} itens")
        print(f"   🎬 Filmes: {summary['movies']}")
        print(f"   📺 Séries: {summary['series']}")
        
        # Mostra exemplos
        if most_watched_movies:
            print(f"\n{'='*70}")
            print("EXEMPLO DE FILME:")
            print('='*70)
            movie = most_watched_movies[0]
            print(f"\n🎬 {movie['title']}")
            print(f"   📅 Ano: {movie['year']}")
            print(f"   ⏱️  Duração: {movie['duration_or_seasons']}")
            print(f"   ⭐ IMDb: {movie['imdb']}")
            if movie.get('player_url'):
                print(f"   🎮 Player: {movie['player_url'][:60]}...")
            if movie.get('video_url'):
                print(f"   🎥 Vídeo: {movie['video_url'][:80]}...")
        
        if most_watched_series:
            print(f"\n{'='*70}")
            print("EXEMPLO DE SÉRIE:")
            print('='*70)
            series = most_watched_series[0]
            print(f"\n📺 {series['title']}")
            print(f"   📅 Ano: {series['year']}")
            print(f"   📺 Temporadas: {series['duration_or_seasons']}")
            print(f"   ⭐ IMDb: {series['imdb']}")
            print(f"   📼 Episódios extraídos: {len(series['episodes'])}")
            
            if series['episodes']:
                print(f"\n   Primeiro episódio:")
                ep = series['episodes'][0]
                print(f"   - {ep['title']}")
                if ep.get('player_url'):
                    print(f"     🎮 Player: {ep['player_url'][:60]}...")
                if ep.get('video_url'):
                    print(f"     🎥 Vídeo: {ep['video_url'][:80]}...")
        
        # Salva resultados organizados
        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'summary': summary,
            'movies': most_watched_movies,
            'series': most_watched_series
        }
    else:
        # Formato antigo (lista simples)
        most_watched = result
        
        if most_watched:
            print("\n" + "="*70)
            print(f"RESULTADOS: {len(most_watched)} FILMES")
            print("="*70)
            
            for i, movie in enumerate(most_watched[:3], 1):
                print(f"\n🎬 {i}. {movie['title']}")
                print(f"   📅 Ano: {movie['year']}")
                print(f"   ⏱️  Duração: {movie['duration_or_seasons']}")
                print(f"   ⭐ IMDb: {movie['imdb']}")
                if movie.get('player_url'):
                    print(f"   🎮 Player: {movie['player_url'][:60]}...")
                if movie.get('video_url'):
                    print(f"   🎥 Vídeo: {movie['video_url'][:80]}...")
        
        # Salva resultados
        output = {
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total': len(most_watched),
            'movies': most_watched
        }
    
    with open('cnvsweb_results.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Resultados salvos em cnvsweb_results.json")


if __name__ == "__main__":
    main()
