import json
import urllib.request
import urllib.error

class HttpClient:
    def post(self, url, payload, custom_headers=None):
        headers = {'Content-Type': 'application/json'}
        if custom_headers:
            headers.update(custom_headers)
            
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=data, headers=headers, method='POST')
        
        try:
            with urllib.request.urlopen(req) as response:
                result = response.read().decode('utf-8')
                return {"status": "sucesso", "dados": result}
        except urllib.error.URLError as e:
            print(f"Erro na requisição POST para {url}: {e}")
            return {"status": "erro", "mensagem": str(e)}
