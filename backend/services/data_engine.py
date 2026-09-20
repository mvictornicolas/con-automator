import pandas as pd
import re
import os
from io import BytesIO
from typing import Tuple, List

class DataEngine:
    
    @staticmethod
    def extract_cpfs_from_text(text: str) -> List[str]:
        """Extrai e normaliza CPFs de um texto livre"""
        # Regex básico para CPF (com ou sem pontuação)
        # Este regex captura 11 dígitos, ignorando pontos e traços.
        # Ex: "123.456.789-00" ou "12345678900"
        raw_cpfs = re.findall(r'(?:\d[^\d]*){11}', text)
        
        normalized = []
        for raw in raw_cpfs:
            clean = re.sub(r'\D', '', raw)
            if len(clean) == 11:
                normalized.append(clean)
        
        # Remove duplicatas mantendo a ordem
        return list(dict.fromkeys(normalized))

    @staticmethod
    def process_file_input(file_content: bytes, filename: str, preferred_col: str = None) -> Tuple[pd.DataFrame, str]:
        """
        Recebe o conteúdo do arquivo, descobre se é CSV, XLS ou TXT,
        encontra a linha de cabeçalho, limpa os dados e extrai a coluna alvo (CPF ou Matrícula).
        """
        ext = filename.split('.')[-1].lower()
        
        if ext == 'csv':
            # Tenta ler as primeiras linhas puras para achar onde está o cabeçalho
            try:
                raw_df = pd.read_csv(BytesIO(file_content), encoding='utf-8', header=None, nrows=20, sep=';')
                encoding = 'utf-8'
            except UnicodeDecodeError:
                raw_df = pd.read_csv(BytesIO(file_content), encoding='iso-8859-1', header=None, nrows=20, sep=';')
                encoding = 'iso-8859-1'
                
            skip_idx = 0
            for i, row in raw_df.iterrows():
                row_str = ' '.join(str(val).lower() for val in row)
                if 'cpf' in row_str or 'matricula' in row_str or 'matrícula' in row_str:
                    skip_idx = i
                    break
            
            df = pd.read_csv(BytesIO(file_content), encoding=encoding, skiprows=skip_idx, sep=';')
            
        elif ext in ['xls', 'xlsx']:
            raw_df = pd.read_excel(BytesIO(file_content), header=None, nrows=20)
            skip_idx = 0
            for i, row in raw_df.iterrows():
                row_str = ' '.join(str(val).lower() for val in row)
                if 'cpf' in row_str or 'matricula' in row_str or 'matrícula' in row_str:
                    skip_idx = i
                    break
            df = pd.read_excel(BytesIO(file_content), skiprows=skip_idx)
            
        elif ext == 'txt':
            text = file_content.decode('utf-8', errors='ignore')
            # Extrai linhas brutas removendo vazias, serve tanto para CPF quanto Matricula
            items = [line.strip() for line in text.split('\n') if line.strip()]
            df = pd.DataFrame({"INPUT_DADO": items})
            return df, "INPUT_DADO"
        else:
            raise ValueError("Formato de arquivo não suportado")
            
        # Para CSV/Excel, descobrir a coluna de CPF/Matricula
        target_col = None
        
        # 1. Tentar encontrar a coluna preferida primeiro (Ex: se o usuário escolheu 'matricula' no front)
        if preferred_col:
            for col in df.columns:
                col_lower = str(col).lower()
                pref_lower = preferred_col.lower()
                if pref_lower in col_lower or (pref_lower == 'matricula' and 'matrícula' in col_lower):
                    target_col = col
                    break
                    
        # 2. Se não achou a preferida (ou não foi enviada), faz o fallback padrão
        if not target_col:
            for col in df.columns:
                if 'cpf' in str(col).lower() or 'matricula' in str(col).lower() or 'matrícula' in str(col).lower():
                    target_col = col
                    break
                
        # 3. Se não achou no cabeçalho, pegar a primeira coluna por padrão
        if not target_col:
            target_col = df.columns[0]
            
        # Limpa espaços e formata a coluna alvo
        df[target_col] = df[target_col].astype(str).str.strip()
        
        # NORMALIZAÇÃO: Remove linhas em branco (ou que viraram "nan" no pandas)
        df = df[df[target_col] != "nan"]
        df = df[df[target_col] != ""]
        
        # NORMALIZAÇÃO: Remove duplicatas baseando-se na Matrícula/CPF, mantendo a 1ª ocorrência
        df = df.drop_duplicates(subset=[target_col], keep='first')
        
        # Reseta a numeração das linhas após as remoções
        df = df.reset_index(drop=True)
        
        return df, target_col

    @staticmethod
    def merge_results_and_save(original_df: pd.DataFrame, cpf_col: str, results: List[dict], output_path: str):
        """
        Faz um JOIN dos resultados da automação com o DataFrame original usando o CPF.
        Isso preserva as colunas originais!
        """
        if not results:
            results_df = pd.DataFrame(columns=['cpf'])
        else:
            results_df = pd.DataFrame(results)
            
        # Garante que a coluna de merge tenha o mesmo tipo
        results_df['cpf'] = results_df['cpf'].astype(str)
        
        # Realiza o left join
        merged_df = pd.merge(original_df, results_df, left_on=cpf_col, right_on='cpf', how='left')
        
        # Remove a coluna 'cpf' duplicada gerada pelo merge se o nome original não for 'cpf'
        if cpf_col.lower() != 'cpf' and 'cpf' in merged_df.columns:
            merged_df = merged_df.drop('cpf', axis=1)
            
        # Salva o resultado
        ext = output_path.split('.')[-1].lower()
        if ext == 'csv':
            # Exportar com UTF-8-SIG (com BOM) e sep=';' garante que o Excel BR abra tudo nas colunas certinhas!
            merged_df.to_csv(output_path, index=False, encoding='utf-8-sig', sep=';')
        elif ext in ['xls', 'xlsx']:
            merged_df.to_excel(output_path, index=False)
