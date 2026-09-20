from abc import ABC, abstractmethod
from typing import Dict, Any, List

class BaseRPAProvider(ABC):
    """
    Classe base para todos os módulos RPA.
    Cada site automatizado deve implementar essa interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Identificador único do plugin (ex: 'site_xyz')"""
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """Nome legível para a interface web"""
        pass

    @property
    @abstractmethod
    def required_configs(self) -> List[Dict[str, str]]:
        """
        Lista de dicionários definindo as variáveis necessárias.
        Ex: [{"key": "username", "label": "Usuário", "type": "text"},
             {"key": "password", "label": "Senha", "type": "password"}]
        """
        pass

    @abstractmethod
    def execute(self, cpfs: List[str], config: Dict[str, Any], progress_callback=None) -> List[Dict[str, Any]]:
        """
        Executa a automação.
        Recebe a lista de CPFs, as configurações (credentials) e uma função de callback
        para atualizar o progresso na UI.
        Retorna uma lista de dicionários com os resultados para cada CPF.
        """
        pass
