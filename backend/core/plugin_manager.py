import importlib
import pkgutil
import inspect
import rpa_modules
from rpa_modules.base import BaseRPAProvider

class PluginManager:
    def __init__(self):
        self.plugins = {}
        self.load_plugins()

    def load_plugins(self):
        """Carrega os plugins da pasta rpa_modules de forma compativel com PyInstaller"""
        from rpa_modules.site_consignet import SiteConsignet
        
        # Hardcoded registration for PyInstaller
        plugins_to_load = [SiteConsignet]
        
        for obj in plugins_to_load:
            instance = obj()
            self.plugins[instance.name] = instance
            print(f"[PluginManager] Carregado plugin: {instance.name}")

    def get_plugin(self, name: str) -> BaseRPAProvider:
        return self.plugins.get(name)

    def get_all_plugins_info(self):
        """Retorna as informações dos plugins para a interface web renderizar"""
        info = []
        for name, plugin in self.plugins.items():
            info.append({
                "name": plugin.name,
                "display_name": plugin.display_name,
                "required_configs": plugin.required_configs
            })
        return info

# Instância global do gerenciador
manager = PluginManager()
