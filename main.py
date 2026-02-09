from flask import Flask, jsonify, request
from flask_cors import CORS
from cnvsweb_scraper import CNVSWebScraper
import threading
import time
import os

app = Flask(__name__)
CORS(app)

# Token de acesso (pode vir de variável de ambiente)
TOKEN = os.environ.get('TOKEN', 'E22PFZRX')

# Inicializa o scraper globalmente
scraper = None
scraper_ready = False

def initialize_scraper():
    """Inicializa o scraper em background"""
    global scraper, scraper_ready
    try:
        print("🚀 Inicializando scraper...")
        scraper = CNVSWebScraper(TOKEN)
        if scraper.login():
            scraper_ready = True
            print("✓ Scraper inicializado com sucesso")
        else:
            print("✗ Erro ao fazer login")
    except Exception as e:
        print(f"✗ Erro ao inicializar scraper: {e}")
        import traceback
        traceback.print_exc()

# Thread para manter a sessão ativa
def keep_session_alive():
    """Mantém a sessão ativa a cada 3 minutos"""
    while True:
        time.sleep(180)  # 3 minutos
        try:
            if scraper and scraper_ready:
                scraper.keep_alive()
        except Exception as e:
            print(f"Erro no keep-alive: {e}")

# Inicia o scraper em background
init_thread = threading.Thread(target=initialize_scraper, daemon=True)
init_thread.start()

# Aguarda até 15 segundos para o scraper estar pronto
print("⏳ Aguardando scraper ficar pronto...")
for i in range(15):
    if scraper_ready:
        print(f"✓ Scraper pronto após {i+1} segundos")
        break
    time.sleep(1)

# Inicia thread de keep-alive
keep_alive_thread = threading.Thread(target=keep_session_alive, daemon=True)
keep_alive_thread.start()

@app.route('/')
def home():
    """Página inicial com informações da API"""
    return jsonify({
        'status': 'online',
        'scraper_ready': scraper_ready,
        'message': 'CNVSWeb Scraper API - Versão Otimizada',
        'version': '4.0.0',
        'endpoints': {
            'most_watched': {
                'url': '/api/most-watched',
                'method': 'GET',
                'description': 'Filmes/séries mais assistidos (PODE SER LENTO se get_video_urls=true)',
                'params': {
                    'limit': 'Opcional - Número máximo de resultados',
                    'max_episodes': 'Opcional - Máximo de episódios por série (padrão: 5)',
                    'organize': 'Opcional - true/false (padrão: true)'
                }
            },
            'catalog_fast': {
                'url': '/api/catalog',
                'method': 'GET',
                'description': '⚡ RÁPIDO - Lista catálogo SEM links de vídeo (< 1s)',
                'params': {
                    'limit': 'Opcional - Número máximo de resultados',
                    'type': 'Opcional - movie/series/all (padrão: all)'
                },
                'example': '/api/catalog?limit=50&type=movie'
            },
            'search': {
                'url': '/api/search?q=query',
                'method': 'GET',
                'description': 'Busca com URLs de vídeo (PODE SER LENTO)',
                'params': {
                    'q': 'Obrigatório - Termo de busca',
                    'limit': 'Opcional - Número máximo de resultados',
                    'max_episodes': 'Opcional - Máximo de episódios por série'
                }
            },
            'search_fast': {
                'url': '/api/search-fast?q=query',
                'method': 'GET',
                'description': '⚡ RÁPIDO - Busca SEM links de vídeo',
                'params': {
                    'q': 'Obrigatório - Termo de busca',
                    'limit': 'Opcional - Número máximo de resultados'
                },
                'example': '/api/search-fast?q=batman&limit=10'
            },
            'video_url': {
                'url': '/api/video-url',
                'method': 'POST',
                'description': '🎥 Busca link direto SOB DEMANDA (quando usuário clica Assistir)',
                'body': {
                    'player_url': 'URL do player do conteúdo'
                },
                'example': 'POST com {"player_url": "https://cnvsweb.stream/watch/123"}'
            }
        },
        'notes': [
            '⚡ NOVOS ENDPOINTS RÁPIDOS: /api/catalog e /api/search-fast',
            '🎥 Link direto sob demanda: /api/video-url (POST)',
            'Endpoints antigos continuam funcionando normalmente',
            'Use endpoints rápidos para melhor experiência'
        ]
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy' if scraper_ready else 'initializing',
        'scraper_ready': scraper_ready,
        'timestamp': time.time()
    })

# ========== ENDPOINTS ANTIGOS (mantidos para compatibilidade) ==========

@app.route('/api/most-watched')
def most_watched():
    """Retorna os filmes/séries mais assistidos do dia COM URLs de vídeo - ORGANIZADO"""
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Scraper ainda está inicializando. Tente novamente em alguns segundos.'
        }), 503
    
    try:
        limit = request.args.get('limit', type=int)
        max_episodes = request.args.get('max_episodes', default=5, type=int)
        organize = request.args.get('organize', default='true', type=str).lower() == 'true'
        
        print("\n" + "="*50)
        print("Extraindo filmes mais assistidos do dia...")
        print("="*50 + "\n")
        
        result = scraper.get_most_watched_today(
            get_video_urls=True,
            max_episodes_per_series=max_episodes,
            organize_output=organize
        )
        
        # Se retornou dados organizados
        if isinstance(result, dict) and 'movies' in result:
            movies = result['movies']
            series = result['series']
            
            # Aplica limite se especificado
            if limit and limit > 0:
                movies = movies[:limit]
                series = series[:limit]
            
            return jsonify({
                'success': True,
                'summary': {
                    'total': result['summary']['total'],
                    'movies': len(movies),
                    'series': len(series)
                },
                'movies': movies,
                'series': series
            })
        else:
            # Formato antigo (lista simples)
            if limit and limit > 0:
                result = result[:limit]
            
            return jsonify({
                'success': True,
                'count': len(result),
                'data': result
            })
    except Exception as e:
        print(f"Erro em /api/most-watched: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search')
def search():
    """Busca filmes/séries por query COM URLs de vídeo - ORGANIZADO"""
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Scraper ainda está inicializando. Tente novamente em alguns segundos.'
        }), 503
    
    query = request.args.get('q', '')
    limit = request.args.get('limit', type=int)
    max_episodes = request.args.get('max_episodes', default=5, type=int)
    organize = request.args.get('organize', default='true', type=str).lower() == 'true'
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query parameter "q" is required',
            'example': '/api/search?q=avengers'
        }), 400
    
    try:
        print("\n" + "="*50)
        print(f"Buscando: {query}")
        print("="*50 + "\n")
        
        result = scraper.search_movies(
            query,
            get_video_urls=True,
            max_episodes_per_series=max_episodes,
            organize_output=organize
        )
        
        # Se retornou dados organizados
        if isinstance(result, dict) and 'movies' in result:
            movies = result['movies']
            series = result['series']
            
            # Aplica limite se especificado
            if limit and limit > 0:
                movies = movies[:limit]
                series = series[:limit]
            
            return jsonify({
                'success': True,
                'query': query,
                'summary': {
                    'total': result['summary']['total'],
                    'movies': len(movies),
                    'series': len(series)
                },
                'movies': movies,
                'series': series
            })
        else:
            # Formato antigo (lista simples)
            if limit and limit > 0:
                result = result[:limit]
            
            return jsonify({
                'success': True,
                'query': query,
                'count': len(result),
                'data': result
            })
    except Exception as e:
        print(f"Erro em /api/search: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search-fast')
def search_fast():
    """Busca filmes/séries por query SEM URLs de vídeo (mais rápido) - ORGANIZADO"""
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Scraper ainda está inicializando. Tente novamente em alguns segundos.'
        }), 503
    
    query = request.args.get('q', '')
    limit = request.args.get('limit', type=int)
    organize = request.args.get('organize', default='true', type=str).lower() == 'true'
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Query parameter "q" is required',
            'example': '/api/search-fast?q=batman'
        }), 400
    
    try:
        print(f"\nBusca rápida: {query}")
        result = scraper.search_movies(
            query,
            get_video_urls=False,  # RÁPIDO!
            max_episodes_per_series=0,
            organize_output=organize
        )
        
        # Se retornou dados organizados
        if isinstance(result, dict) and 'movies' in result:
            movies = result['movies']
            series = result['series']
            
            # Aplica limite se especificado
            if limit and limit > 0:
                movies = movies[:limit]
                series = series[:limit]
            
            return jsonify({
                'success': True,
                'query': query,
                'summary': {
                    'total': result['summary']['total'],
                    'movies': len(movies),
                    'series': len(series)
                },
                'movies': movies,
                'series': series
            })
        else:
            # Formato antigo (lista simples)
            if limit and limit > 0:
                result = result[:limit]
            
            return jsonify({
                'success': True,
                'query': query,
                'count': len(result),
                'data': result
            })
    except Exception as e:
        print(f"Erro em /api/search-fast: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# ========== NOVOS ENDPOINTS OTIMIZADOS ==========

@app.route('/api/catalog')
def catalog():
    """
    ⚡ ENDPOINT ULTRA RÁPIDO
    Retorna catálogo SEM buscar links de vídeo
    Perfeito para carregamento inicial de apps
    """
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Scraper ainda está inicializando.'
        }), 503
    
    try:
        limit = request.args.get('limit', type=int)
        content_type = request.args.get('type', default='all', type=str)
        
        print("\n⚡ Carregando catálogo rápido...")
        
        # Usa get_most_watched_today SEM buscar URLs de vídeo
        result = scraper.get_most_watched_today(
            get_video_urls=False,  # RÁPIDO: não busca links
            max_episodes_per_series=0,
            organize_output=True
        )
        
        if isinstance(result, dict) and 'movies' in result:
            movies = result['movies']
            series = result['series']
            
            # Filtra por tipo se especificado
            if content_type == 'movie':
                series = []
            elif content_type == 'series':
                movies = []
            
            # Aplica limite
            if limit and limit > 0:
                movies = movies[:limit]
                series = series[:limit]
            
            return jsonify({
                'success': True,
                'summary': {
                    'total': len(movies) + len(series),
                    'movies': len(movies),
                    'series': len(series)
                },
                'data': {
                    'movies': movies,
                    'series': series
                }
            })
        else:
            # Lista simples
            items = result if isinstance(result, list) else []
            
            if limit and limit > 0:
                items = items[:limit]
            
            return jsonify({
                'success': True,
                'count': len(items),
                'data': items
            })
            
    except Exception as e:
        print(f"Erro em /api/catalog: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/video-url', methods=['POST'])
def get_video_url():
    """
    🎥 ENDPOINT CRÍTICO - Busca link direto SOB DEMANDA
    Recebe player_url e retorna video_url
    Chamado quando usuário clica em "Assistir"
    """
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Scraper não está pronto.'
        }), 503
    
    data = request.get_json()
    if not data or 'player_url' not in data:
        return jsonify({
            'success': False,
            'error': 'Campo "player_url" obrigatório no body JSON',
            'example': '{"player_url": "https://cnvsweb.stream/watch/123"}'
        }), 400
    
    player_url = data['player_url']
    
    try:
        print(f"\n🎥 Buscando link de vídeo para: {player_url}")
        
        # Usa método do scraper original para extrair vídeo
        video_url = scraper.get_video_url_from_player(player_url)
        
        if video_url:
            print(f"✓ Link obtido: {video_url[:80]}...")
            return jsonify({
                'success': True,
                'video_url': video_url,
                'player_url': player_url
            })
        else:
            print("✗ Não foi possível extrair URL do vídeo")
            return jsonify({
                'success': False,
                'error': 'Não foi possível extrair URL do vídeo'
            }), 404
            
    except Exception as e:
        print(f"Erro em /api/video-url: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Tratamento de erros 404
@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint not found',
        'available_endpoints': [
            '/',
            '/health',
            '/api/most-watched',
            '/api/catalog (RÁPIDO)',
            '/api/search?q=query',
            '/api/search-fast?q=query (RÁPIDO)',
            '/api/video-url (POST - SOB DEMANDA)'
        ]
    }), 404

if __name__ == '__main__':
    # Porta configurável para deploy
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Servidor rodando em http://0.0.0.0:{port}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
