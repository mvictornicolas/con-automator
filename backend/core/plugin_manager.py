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
        """Descobre dinamicamente e carrega os plugins da pasta rpa_modules"""
        # Itera sobre todos os módulos dentro de rpa_modules
        for _, module_name, _ in pkgutil.iter_modules(rpa_modules.__path__):
            module = importlib.import_module(f"rpa_modules.{module_name}")
            
            # Encontra as classes que herdam de BaseRPAProvider (ignorando a própria base)
            for name, obj in inspect.getmembers(module, inspect.isclass):
                if issubclass(obj, BaseRPAProvider) and obj is not BaseRPAProvider:
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
