import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin
import json
from functools import lru_cache

class CNVSWebScraper:
    """
    Versão OTIMIZADA do scraper para streaming
    Foco em VELOCIDADE e performance
    """
    
    def __init__(self, token):
        self.base_url = "https://cnvsweb.stream"
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://cnvsweb.stream/',
        })
        self.last_activity = time.time()
        self.logged_in = False
        
        # Timeout otimizado
        self.timeout = 10
        
    def login(self):
        """Login otimizado"""
        try:
            login_page_url = f"{self.base_url}/login"
            login_ajax_url = f"{self.base_url}/ajax/login.php"
            
            # GET rápido
            self.session.get(login_page_url, timeout=self.timeout)
            
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
            
            ajax_headers = {
                'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
                'X-Requested-With': 'XMLHttpRequest',
                'Accept': 'application/json, text/javascript, */*; q=0.01',
                'Origin': self.base_url,
                'Referer': login_page_url
            }
            
            response = self.session.post(
                login_ajax_url, 
                data=payload, 
                headers=ajax_headers,
                allow_redirects=False,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    
                    if data.get('status') == 'success':
                        redirect_url = data.get('redirect', self.base_url)
                        response = self.session.get(redirect_url, timeout=self.timeout)
                        
                        if response.status_code == 200 and '/login' not in response.url:
                            self.last_activity = time.time()
                            self.logged_in = True
                            print("✓ Login OK")
                            return True
                    
                    return False
                except:
                    return False
            
            return False
                
        except Exception as e:
            print(f"Erro login: {e}")
            return False
    
    def keep_alive(self):
        """Mantém sessão"""
        if not self.logged_in:
            return
            
        current_time = time.time()
        if current_time - self.last_activity > 180:
            try:
                self.session.get(self.base_url, timeout=5)
                self.last_activity = time.time()
            except:
                pass
    
    def get_catalog_fast(self, limit=50, content_type='all'):
        """
        ⚡ MÉTODO ULTRA RÁPIDO
        Retorna catálogo SEM extrair links de vídeo
        Ideal para carregar lista inicial do app
        """
        self.keep_alive()
        
        try:
            response = self.session.get(self.base_url, timeout=self.timeout)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            items = []
            
            # Procura seção "Mais Visto"
            all_h5 = soup.find_all('h5')
            most_watched_section = None
            
            for h5 in all_h5:
                if h5.text and 'Mais Visto' in h5.text:
                    most_watched_section = h5
                    break
            
            if not most_watched_section:
                return {'items': [], 'count': 0}
            
            container = most_watched_section.find_parent('div', class_='col-12')
            if not container:
                return {'items': [], 'count': 0}
            
            # Extrai items
            slides = container.find_all('div', class_='swiper-slide')
            if not slides:
                slides = container.find_all('div', class_='item')
            
            for item in slides[:limit]:
                try:
                    info_div = item.find('div', class_='info')
                    if not info_div:
                        continue
                    
                    # Título
                    title_tag = info_div.find('h6')
                    title = title_tag.text.strip() if title_tag else "Sem título"
                    
                    # Link player
                    watch_btn = info_div.find('a', href=True)
                    player_url = watch_btn['href'] if watch_btn else ""
                    
                    # Extrai ID do player_url
                    item_id = ""
                    if player_url:
                        match = re.search(r'/(\d+)/?$', player_url)
                        if match:
                            item_id = match.group(1)
                    
                    # Tags
                    tags = info_div.find('p', class_='tags')
                    duration = ""
                    year = ""
                    imdb = ""
                    
                    if tags:
                        spans = tags.find_all('span')
                        if len(spans) >= 1:
                            duration = spans[0].text.strip()
                        if len(spans) >= 2:
                            year = spans[1].text.strip()
                        if len(spans) >= 3:
                            imdb = spans[2].text.strip()
                    
                    # Poster
                    poster_div = item.find('div', class_='poster')
                    poster = ""
                    if poster_div:
                        img_tag = poster_div.find('img')
                        if img_tag and img_tag.get('src'):
                            poster = img_tag['src']
                    
                    # Tipo (movie ou series)
                    is_series = 'temporada' in duration.lower() or 'temp' in duration.lower()
                    content_type_item = 'series' if is_series else 'movie'
                    
                    # Filtra por tipo se especificado
                    if content_type != 'all' and content_type != content_type_item:
                        continue
                    
                    item_data = {
                        'id': item_id,
                        'title': title,
                        'type': content_type_item,
                        'duration_or_seasons': duration,
                        'year': year,
                        'imdb': imdb,
                        'poster': poster,
                        'player_url': player_url
                        # NÃO inclui video_url - será buscado sob demanda
                    }
                    
                    items.append(item_data)
                    
                except Exception as e:
                    continue
            
            return {
                'items': items,
                'count': len(items),
                'type': content_type
            }
            
        except Exception as e:
            print(f"Erro get_catalog_fast: {e}")
            return {'items': [], 'count': 0}
    
    def search_fast(self, query, limit=20):
        """
        🔍 BUSCA RÁPIDA
        Retorna resultados SEM links de vídeo
        """
        self.keep_alive()
        
        try:
            search_url = f"{self.base_url}/search"
            params = {'q': query}
            
            response = self.session.get(search_url, params=params, timeout=self.timeout)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            items = []
            
            # Procura resultados
            results = soup.find_all('div', class_='item')
            
            for item in results[:limit]:
                try:
                    info_div = item.find('div', class_='info')
                    if not info_div:
                        continue
                    
                    # Título
                    title_tag = info_div.find('h6')
                    title = title_tag.text.strip() if title_tag else "Sem título"
                    
                    # Link
                    watch_btn = info_div.find('a', href=True)
                    player_url = watch_btn['href'] if watch_btn else ""
                    
                    # ID
                    item_id = ""
                    if player_url:
                        match = re.search(r'/(\d+)/?$', player_url)
                        if match:
                            item_id = match.group(1)
                    
                    # Tags
                    tags = info_div.find('p', class_='tags')
                    duration = ""
                    year = ""
                    imdb = ""
                    
                    if tags:
                        spans = tags.find_all('span')
                        if len(spans) >= 1:
                            duration = spans[0].text.strip()
                        if len(spans) >= 2:
                            year = spans[1].text.strip()
                        if len(spans) >= 3:
                            imdb = spans[2].text.strip()
                    
                    # Poster
                    poster_div = item.find('div', class_='poster')
                    poster = ""
                    if poster_div:
                        img_tag = poster_div.find('img')
                        if img_tag and img_tag.get('src'):
                            poster = img_tag['src']
                    
                    # Tipo
                    is_series = 'temporada' in duration.lower() or 'temp' in duration.lower()
                    content_type = 'series' if is_series else 'movie'
                    
                    item_data = {
                        'id': item_id,
                        'title': title,
                        'type': content_type,
                        'duration_or_seasons': duration,
                        'year': year,
                        'imdb': imdb,
                        'poster': poster,
                        'player_url': player_url
                    }
                    
                    items.append(item_data)
                    
                except:
                    continue
            
            return {
                'items': items,
                'count': len(items),
                'query': query
            }
            
        except Exception as e:
            print(f"Erro search_fast: {e}")
            return {'items': [], 'count': 0}
    
    def get_video_url_fast(self, player_url):
        """
        🎥 MÉTODO CRÍTICO - Extrai link DIRETO do vídeo
        Otimizado para velocidade máxima
        Chamado SOB DEMANDA quando usuário clica "Assistir"
        """
        try:
            # Request otimizado
            response = self.session.get(player_url, timeout=self.timeout)
            self.last_activity = time.time()
            html = response.text
            soup = BeautifulSoup(html, 'html.parser')
            
            # MÉTODO 1: Tag <video> com <source>
            video_tags = soup.find_all('video')
            for video_tag in video_tags:
                source_tags = video_tag.find_all('source')
                for source_tag in source_tags:
                    src = source_tag.get('src')
                    if src and '.mp4' in src:
                        return src
            
            # MÉTODO 2: Regex otimizado para URLs .mp4
            patterns = [
                r'https?://server[^"\s]*?\.mp4[^"\s]*',
                r'https?://[^"\s]*playmycnvs[^"\s]*?\.mp4[^"\s]*',
                r'"file"["\s]*:["\s]*"([^"]+\.mp4[^"]*)"',
                r'"src"["\s]*:["\s]*"([^"]+\.mp4[^"]*)"',
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, html, re.IGNORECASE)
                if matches:
                    video_url = matches[0]
                    if isinstance(video_url, tuple):
                        video_url = video_url[0]
                    video_url = video_url.strip('"\'\\').strip()
                    if video_url.startswith('http') and '.mp4' in video_url:
                        return video_url
            
            # MÉTODO 3: Busca agressiva
            all_urls = re.findall(r'https?://[^\s<>"\']+\.mp4[^\s<>"\']*', html)
            if all_urls:
                return all_urls[0].strip('"\'\\,;')
            
            return None
            
        except Exception as e:
            print(f"Erro get_video_url_fast: {e}")
            return None
    
    def get_item_details(self, item_id):
        """Busca detalhes de um item específico"""
        try:
            item_url = f"{self.base_url}/watch/{item_id}"
            response = self.session.get(item_url, timeout=self.timeout)
            self.last_activity = time.time()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extrai informações da página
            title_tag = soup.find('h1')
            title = title_tag.text.strip() if title_tag else "Sem título"
            
            # Sinopse
            description_tag = soup.find('div', class_='description')
            description = description_tag.text.strip() if description_tag else ""
            
            # Poster
            poster_tag = soup.find('img', class_='poster')
            poster = poster_tag['src'] if poster_tag and poster_tag.get('src') else ""
            
            return {
                'id': item_id,
                'title': title,
                'description': description,
                'poster': poster,
                'player_url': item_url
            }
            
        except Exception as e:
            print(f"Erro get_item_details: {e}")
            return None
