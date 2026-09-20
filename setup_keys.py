import rsa
import os

print("Gerando par de chaves RSA (1024 bits)... isso pode levar alguns segundos.")
public_key, private_key = rsa.newkeys(1024)

# Salva a chave privada
with open("private_key.pem", "wb") as priv_file:
    priv_file.write(private_key.save_pkcs1())

# Salva a chave publica
with open("public_key.pem", "wb") as pub_file:
    pub_file.write(public_key.save_pkcs1())

print("Chaves geradas com sucesso!")
