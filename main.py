from flask import Flask, jsonify, request
from cnvsweb_scraper import CNVSWebScraper
import threading
import time
import os

app = Flask(__name__)

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
        'message': 'CNVSWeb Scraper API - Versão Organizada',
        'version': '3.0.0',
        'endpoints': {
            'most_watched': {
                'url': '/api/most-watched',
                'method': 'GET',
                'description': 'Filmes/séries mais assistidos do dia (ORGANIZADO)',
                'params': {
                    'limit': 'Opcional - Número máximo de resultados (padrão: todos)',
                    'max_episodes': 'Opcional - Máximo de episódios por série (padrão: 5)',
                    'organize': 'Opcional - true/false (padrão: true)'
                },
                'example': '/api/most-watched?limit=10&max_episodes=3'
            },
            'search': {
                'url': '/api/search?q=query',
                'method': 'GET',
                'description': 'Busca filmes/séries com URLs de vídeo (ORGANIZADO)',
                'params': {
                    'q': 'Obrigatório - Termo de busca',
                    'limit': 'Opcional - Número máximo de resultados',
                    'max_episodes': 'Opcional - Máximo de episódios por série (padrão: 5)',
                    'organize': 'Opcional - true/false (padrão: true)'
                },
                'example': '/api/search?q=avengers&limit=10&max_episodes=3'
            },
            'search_fast': {
                'url': '/api/search-fast?q=query',
                'method': 'GET',
                'description': 'Busca rápida sem URLs de vídeo (ORGANIZADO)',
                'params': {
                    'q': 'Obrigatório - Termo de busca',
                    'limit': 'Opcional - Número máximo de resultados',
                    'organize': 'Opcional - true/false (padrão: true)'
                },
                'example': '/api/search-fast?q=batman&limit=5'
            }
        },
        'notes': [
            'NOVA VERSÃO: Dados organizados em {movies: [], series: []}',
            'Campo "type" indica se é "movie" ou "series"',
            'Parâmetro max_episodes limita episódios por série',
            'organize=false retorna formato antigo (lista simples)',
            'URLs de vídeo são válidas por tempo limitado',
            'A sessão é mantida automaticamente a cada 3 minutos'
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
            get_video_urls=False,
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
            '/api/search?q=query',
            '/api/search-fast?q=query'
        ]
    }), 404

if __name__ == '__main__':
    # Porta configurável para deploy
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
