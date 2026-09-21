import tkinter as tk
from tkinter import ttk, messagebox
import json
import base64
import rsa
import os
from datetime import datetime, timedelta

def load_private_key():
    try:
        with open("private_key.pem", "rb") as f:
            return rsa.PrivateKey.load_pkcs1(f.read())
    except Exception as e:
        messagebox.showerror("Erro Crítico", f"Falha ao carregar private_key.pem!\n{e}")
        return None

PRIVATE_KEY = load_private_key()

def generate_token(hwid: str, days_valid: int, tier: str = "ultimate"):
    exp_date = datetime.now() + timedelta(days=days_valid)
    payload = {
        "hwid": hwid.strip(),
        "exp": exp_date.isoformat(),
        "tier": tier
    }
    payload_json = json.dumps(payload)
    b64_payload = base64.b64encode(payload_json.encode('utf-8')).decode('utf-8')
    signature = rsa.sign(b64_payload.encode('utf-8'), PRIVATE_KEY, 'SHA-256')
    signature_b64 = base64.b64encode(signature).decode('utf-8')
    return f"{b64_payload}.{signature_b64}", exp_date

def on_generate():
    if not PRIVATE_KEY:
        messagebox.showerror("Erro", "Chave privada não encontrada.")
        return
        
    hwid = hwid_entry.get().strip()
    if not hwid:
        messagebox.showwarning("Aviso", "O campo HWID não pode estar vazio.")
        return
        
    try:
        days = int(days_entry.get())
    except ValueError:
        messagebox.showwarning("Aviso", "Dias de validade deve ser um número inteiro.")
        return
        
    tier_map = {
        "Basic (Max 400 consultas/dia, 1.0x vel)": "basic",
        "Medium (Max 800 consultas/dia, 3.3x vel)": "medium",
        "Ultimate (Sem limites, vel. max)": "ultimate"
    }
    tier = tier_map.get(tier_combobox.get(), "ultimate")
    
    try:
        token, exp = generate_token(hwid, days, tier)
        token_text.config(state='normal')
        token_text.delete('1.0', tk.END)
        token_text.insert(tk.END, token)
        token_text.config(state='disabled')
        
        info_label.config(text=f"Válido até: {exp.strftime('%d/%m/%Y %H:%M')}\nNível: {tier.upper()}", fg="green")
    except Exception as e:
        messagebox.showerror("Erro", f"Ocorreu um erro ao gerar o token:\n{e}")

def copy_to_clipboard():
    token = token_text.get('1.0', tk.END).strip()
    if token:
        root.clipboard_clear()
        root.clipboard_append(token)
        root.update() # Keeps clipboard in memory after window closed
        messagebox.showinfo("Copiado", "Token copiado para a área de transferência!")
    else:
        messagebox.showwarning("Aviso", "Nenhum token para copiar.")

root = tk.Tk()
root.title("Gerador de Licenças RPA")
root.geometry("500x450")
root.configure(padx=20, pady=20)
root.resizable(False, False)

# Se nao tiver a chave, desabilita a interface
if not PRIVATE_KEY:
    tk.Label(root, text="Chave privada não encontrada!\nFeche, coloque o private_key.pem na pasta e tente novamente.", fg="red").pack(pady=20)
else:
    # HWID
    tk.Label(root, text="Hardware ID (HWID) do Cliente:", font=("Arial", 10, "bold")).pack(anchor="w")
    hwid_entry = tk.Entry(root, width=50, font=("Consolas", 10))
    hwid_entry.pack(fill="x", pady=(0, 15))

    # Validade
    tk.Label(root, text="Validade (em dias):", font=("Arial", 10, "bold")).pack(anchor="w")
    days_entry = tk.Entry(root, width=10, font=("Consolas", 10))
    days_entry.insert(0, "30")
    days_entry.pack(anchor="w", pady=(0, 15))

    # Tier (Nivel)
    tk.Label(root, text="Plano / Nível da Licença:", font=("Arial", 10, "bold")).pack(anchor="w")
    tier_combobox = ttk.Combobox(root, state="readonly", width=45, font=("Arial", 10))
    tier_combobox['values'] = (
        "Basic (Max 400 consultas/dia, 1.0x vel)",
        "Medium (Max 800 consultas/dia, 3.3x vel)",
        "Ultimate (Sem limites, vel. max)"
    )
    tier_combobox.current(2) # Default Ultimate
    tier_combobox.pack(anchor="w", pady=(0, 20))

    # Generate Button
    generate_btn = tk.Button(root, text="GERAR TOKEN", bg="#0052cc", fg="white", font=("Arial", 10, "bold"), command=on_generate, height=2)
    generate_btn.pack(fill="x", pady=(0, 10))
    
    # Info Label
    info_label = tk.Label(root, text="", font=("Arial", 9, "bold"))
    info_label.pack()

    # Token Text
    tk.Label(root, text="Token Gerado:", font=("Arial", 10, "bold")).pack(anchor="w", pady=(10, 0))
    token_text = tk.Text(root, height=4, width=50, font=("Consolas", 9), state='disabled')
    token_text.pack(fill="x", pady=(2, 5))
    
    # Copy Button
    copy_btn = tk.Button(root, text="Copiar para a Área de Transferência", command=copy_to_clipboard)
    copy_btn.pack(anchor="e")

root.mainloop()
