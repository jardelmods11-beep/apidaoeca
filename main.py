from flask import Flask, jsonify, request
from flask_cors import CORS
from cnvsweb_scraper_fast import CNVSWebScraperFast
import threading
import time
import os
from functools import lru_cache
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)
CORS(app)

# Token de acesso
TOKEN = os.environ.get('TOKEN', 'HJK6V5MH')

# Scraper global
scraper = None
scraper_ready = False

# Thread pool para requests paralelas
executor = ThreadPoolExecutor(max_workers=10)

def initialize_scraper():
    """Inicializa o scraper em background"""
    global scraper, scraper_ready
    try:
        print("🚀 Inicializando scraper otimizado...")
        scraper = CNVSWebScraperFast(TOKEN)
        if scraper.login():
            scraper_ready = True
            print("✓ Scraper pronto para uso!")
        else:
            print("✗ Erro no login")
    except Exception as e:
        print(f"✗ Erro: {e}")

def keep_session_alive():
    """Mantém sessão ativa"""
    while True:
        time.sleep(180)
        try:
            if scraper and scraper_ready:
                scraper.keep_alive()
        except:
            pass

# Inicia scraper
init_thread = threading.Thread(target=initialize_scraper, daemon=True)
init_thread.start()

# Aguarda scraper
print("⏳ Aguardando scraper...")
for i in range(15):
    if scraper_ready:
        print(f"✓ Pronto em {i+1}s")
        break
    time.sleep(1)

# Keep-alive thread
keep_alive_thread = threading.Thread(target=keep_session_alive, daemon=True)
keep_alive_thread.start()

@app.route('/')
def home():
    """Informações da API"""
    return jsonify({
        'status': 'online',
        'version': '4.0.0 - ULTRA FAST',
        'scraper_ready': scraper_ready,
        'endpoints': {
            'catalog': {
                'url': '/api/catalog',
                'method': 'GET',
                'description': '⚡ Lista RÁPIDA de filmes/séries (SEM links)',
                'params': {
                    'limit': 'Limite de resultados (padrão: 50)',
                    'type': 'movie ou series (opcional)'
                },
                'example': '/api/catalog?limit=20&type=movie'
            },
            'search': {
                'url': '/api/search',
                'method': 'GET',
                'description': '🔍 Busca RÁPIDA (SEM links de vídeo)',
                'params': {
                    'q': 'Termo de busca',
                    'limit': 'Limite de resultados'
                },
                'example': '/api/search?q=avengers&limit=10'
            },
            'video_url': {
                'url': '/api/video-url',
                'method': 'POST',
                'description': '🎥 Pega link DIRETO do vídeo (INSTANTÂNEO)',
                'body': {
                    'player_url': 'URL do player do conteúdo'
                },
                'example': 'POST /api/video-url com {"player_url": "..."}'
            },
            'item_details': {
                'url': '/api/item/<item_id>',
                'method': 'GET',
                'description': '📋 Detalhes de filme/série',
                'example': '/api/item/123456'
            }
        },
        'notes': [
            '⚡ NOVA ARQUITETURA OTIMIZADA PARA STREAMING',
            '🚀 Catálogo carrega INSTANTANEAMENTE (sem links)',
            '🎥 Links de vídeo são buscados SOB DEMANDA',
            '⏱️ Tempo de resposta < 300ms para catálogo',
            '🔥 Tempo de resposta < 1s para link direto',
            '💾 Cache inteligente para busca de links'
        ]
    })

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy' if scraper_ready else 'initializing',
        'scraper_ready': scraper_ready,
        'timestamp': time.time()
    })

@app.route('/api/catalog')
def catalog():
    """
    ⚡ ENDPOINT ULTRA RÁPIDO - Lista catálogo SEM links de vídeo
    Retorna em <300ms
    """
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Inicializando... Tente em alguns segundos.'
        }), 503
    
    try:
        limit = request.args.get('limit', default=50, type=int)
        content_type = request.args.get('type', default='all', type=str)
        
        # Busca rápida sem URLs de vídeo
        result = scraper.get_catalog_fast(limit=limit, content_type=content_type)
        
        return jsonify({
            'success': True,
            'count': len(result.get('items', [])),
            'data': result
        })
        
    except Exception as e:
        print(f"Erro em /api/catalog: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/search')
def search():
    """
    🔍 BUSCA RÁPIDA - Sem links de vídeo
    Retorna em <500ms
    """
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Inicializando... Tente em alguns segundos.'
        }), 503
    
    query = request.args.get('q', '')
    limit = request.args.get('limit', default=20, type=int)
    
    if not query:
        return jsonify({
            'success': False,
            'error': 'Parâmetro "q" obrigatório'
        }), 400
    
    try:
        result = scraper.search_fast(query, limit=limit)
        
        return jsonify({
            'success': True,
            'query': query,
            'count': len(result.get('items', [])),
            'data': result
        })
        
    except Exception as e:
        print(f"Erro em /api/search: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/video-url', methods=['POST'])
def get_video_url():
    """
    🎥 ENDPOINT CRÍTICO - Pega link DIRETO do vídeo
    Chamado SOB DEMANDA quando usuário clica em "Assistir"
    Retorna em <1s
    """
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Inicializando...'
        }), 503
    
    data = request.get_json()
    player_url = data.get('player_url')
    
    if not player_url:
        return jsonify({
            'success': False,
            'error': 'player_url obrigatório'
        }), 400
    
    try:
        # Extração OTIMIZADA do link direto
        video_url = scraper.get_video_url_fast(player_url)
        
        if video_url:
            return jsonify({
                'success': True,
                'video_url': video_url,
                'player_url': player_url
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Link de vídeo não encontrado'
            }), 404
            
    except Exception as e:
        print(f"Erro em /api/video-url: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/item/<item_id>')
def item_details(item_id):
    """Detalhes de um item específico"""
    if not scraper_ready:
        return jsonify({
            'success': False,
            'error': 'Inicializando...'
        }), 503
    
    try:
        # Busca detalhes do item
        result = scraper.get_item_details(item_id)
        
        if result:
            return jsonify({
                'success': True,
                'data': result
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Item não encontrado'
            }), 404
            
    except Exception as e:
        print(f"Erro em /api/item: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({
        'success': False,
        'error': 'Endpoint não encontrado',
        'endpoints': [
            '/',
            '/health',
            '/api/catalog',
            '/api/search?q=query',
            '/api/video-url (POST)',
            '/api/item/<id>'
        ]
    }), 404

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    # Usa gevent para performance
    try:
        from gevent.pywsgi import WSGIServer
        print(f"🚀 Servidor rodando em http://0.0.0.0:{port} (Gevent)")
        http_server = WSGIServer(('0.0.0.0', port), app)
        http_server.serve_forever()
    except ImportError:
        print(f"🚀 Servidor rodando em http://0.0.0.0:{port} (Flask)")
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
