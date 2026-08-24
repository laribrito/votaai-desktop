import uuid
import hashlib

class DeviceService:
    def get_device_id(self):
        """
        Gera um identificador único para o dispositivo usando o endereço MAC (hardware).
        Retorna um hash SHA-256 para não expor o MAC real diretamente e garantir tamanho fixo.
        """
        mac_num = uuid.getnode()
        mac_str = ':'.join(('%012X' % mac_num)[i:i+2] for i in range(0, 12, 2))
        
        # Faz um hash para padronizar e ocultar o MAC original
        device_hash = hashlib.sha256(mac_str.encode('utf-8')).hexdigest()
        
        return f"dev-{device_hash[:16]}" # Usa os primeiros 16 caracteres para ser amigável
