"""
Servidor de transcripciones para LAM Historico
Recibe un video_id y devuelve el texto limpio de los subtitulos

Uso:
  python transcript_server.py

Despues en Make, hacer un HTTP GET a:
  http://localhost:5000/transcript?video_id=VIDEO_ID
"""

import re
import os
import sys
import json
import tempfile
import subprocess
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 5000

def limpiar_vtt(texto):
    """Limpia el formato VTT y devuelve solo el texto."""
    lineas = texto.split('\n')
    resultado = []
    visto = set()
    
    for linea in lineas:
        linea = linea.strip()
        # Saltar headers, timestamps y lineas vacias
        if not linea:
            continue
        if linea.startswith('WEBVTT'):
            continue
        if linea.startswith('Kind:'):
            continue
        if linea.startswith('Language:'):
            continue
        if '-->' in linea:
            continue
        if re.match(r'^\d+$', linea):
            continue
        
        # Limpiar etiquetas HTML tipo <00:00:02.360><c>
        linea = re.sub(r'<[^>]+>', '', linea)
        linea = linea.strip()
        
        if not linea:
            continue
            
        # Evitar duplicados consecutivos
        if linea not in visto:
            visto.add(linea)
            resultado.append(linea)
        
        # Limpiar el set cada 10 lineas para no perder contexto
        if len(visto) > 10:
            visto = set(resultado[-5:])
    
    texto_limpio = ' '.join(resultado)
    # Limitar a 8000 caracteres para no explotar el contexto de Claude
    return texto_limpio[:8000]

def obtener_transcripcion(video_id):
    """Baja y limpia los subtitulos de un video de YouTube."""
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, video_id)
        
       cmd = [
    sys.executable, '-m', 'yt_dlp',
    '--write-auto-sub',
    '--sub-lang', 'es',
    '--skip-download',
    '--output', output_path,
    '--quiet',
    '--extractor-args', 'youtube:player_client=web',
    '--user-agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    f'https://www.youtube.com/watch?v={video_id}'
]
        
        try:
            subprocess.run(cmd, capture_output=True, timeout=30)
        except subprocess.TimeoutExpired:
            return None
        
        # Buscar el archivo .vtt generado
        for archivo in os.listdir(tmpdir):
            if archivo.endswith('.vtt'):
                with open(os.path.join(tmpdir, archivo), 'r', encoding='utf-8') as f:
                    contenido = f.read()
                return limpiar_vtt(contenido)
        
        return None

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        
        if parsed.path != '/transcript':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not found')
            return
        
        video_id = params.get('video_id', [None])[0]
        
        if not video_id:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Falta video_id')
            return
        
        print(f'[+] Bajando transcripcion: {video_id}')
        transcripcion = obtener_transcripcion(video_id)
        
        if not transcripcion:
            respuesta = json.dumps({'transcript': '', 'error': 'sin subtitulos'})
        else:
            respuesta = json.dumps({'transcript': transcripcion, 'error': None})
            print(f'[+] OK - {len(transcripcion)} caracteres')
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(respuesta.encode('utf-8'))
    
    def log_message(self, format, *args):
        pass  # Silenciar logs del servidor

if __name__ == '__main__':
    print(f'Servidor corriendo en http://localhost:{PORT}')
    print(f'Ejemplo: http://localhost:{PORT}/transcript?video_id=dSvDn-Ne9m0')
    print('Ctrl+C para detener\n')
    server = HTTPServer(('0.0.0.0', PORT), Handler)
    server.serve_forever()
