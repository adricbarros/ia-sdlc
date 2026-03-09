# Usa a imagem oficial do Python (Baseada em Debian enxugado)
FROM python:3.11-slim

# Define a pasta de trabalho dentro do contêiner
WORKDIR /app

# Instala dependências do sistema para o MySQL e compilação
# CORREÇÃO SONAR: Pacotes em ordem alfabética e bloqueio de pacotes extras inúteis
RUN apt-get update && apt-get install -y --no-install-recommends \
    default-libmysqlclient-dev \
    gcc \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copia o requirements primeiro para otimizar o cache
COPY requirements.txt .

# Instala as bibliotecas Python (Flask, Gunicorn, SQLAlchemy, etc)
RUN pip install --no-cache-dir -r requirements.txt

# Copia o resto do código (exceto o que está no .dockerignore)
COPY . .

# ======================================================================
# CORREÇÃO SONAR (Segurança Crítica): Rodar sem privilégios de Root
# Cria um usuário chamado 'pcauser', dá a ele a posse da pasta /app
# (vital para poder salvar os uploads de imagens) e troca para ele.
# ======================================================================
RUN useradd -m pcauser && chown -R pcauser:pcauser /app
USER pcauser

# Expõe a porta do Flask
EXPOSE 5000

# O comando para ligar o servidor (com preload do Gunicorn ativado)
CMD ["gunicorn", "--preload", "--workers", "3", "--bind", "0.0.0.0:5000", "app:app"]