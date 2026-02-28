import os
# Avisa o sistema que estamos em modo de teste ANTES de carregar a aplicação
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from werkzeug.security import generate_password_hash
# Importe o Usuario (ou o nome do seu model de conta)
from app import app, db, Ente, Secretaria, Usuario 

@pytest.fixture
def client():
    # Configura o Flask para modo de teste
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False # Desativa o token de formulário para facilitar o teste automatizado

    with app.test_client() as client:
        with app.app_context():
            # --- TRAVA DE SEGURANÇA (KILL SWITCH) ---
            if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                raise RuntimeError("⚠️ ALERTA DE SEGURANÇA: O teste tentou conectar em um banco real. Abortando!")
            
            db.create_all()
            
            # Cria dados básicos simulados para a tela carregar sem erro
            ente_teste = Ente(nome="Prefeitura Teste")
            sec_teste = Secretaria(nome="Secretaria de Teste")
            
            # Cria um usuário falso na memória para testarmos o Login
            senha_hasheada = generate_password_hash("senha_segura_123")
            usuario_teste = Usuario(nome="Admin Teste", login="admin", email="admin@teste.com", senha=senha_hasheada)
            
            db.session.add_all([ente_teste, sec_teste, usuario_teste])
            db.session.commit()
            
            yield client
            
            db.session.remove()
            # Limpa o banco para que o próximo teste comece do zero.
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
                db.drop_all()

# --- BLOCO 1: TESTES PÚBLICOS ---

def test_home_page_carrega_com_sucesso(client):
    """Testa se a página pública (Portal) está online (Status 200)"""
    resposta = client.get('/')
    assert resposta.status_code == 200
    assert b"PCA" in resposta.data

def test_erro_404_pagina_nao_encontrada(client):
    """Testa se o sistema lida corretamente com URLs que não existem"""
    resposta = client.get('/uma-url-que-nao-existe-no-sistema')
    assert resposta.status_code == 404

# --- BLOCO 2: TESTES DE AUTENTICAÇÃO ---

def test_login_page_carrega_com_sucesso(client):
    """Testa se a tela de login administrativo está acessível via GET"""
    resposta = client.get('/admin/login')
    assert resposta.status_code == 200

def test_login_falha_com_senha_incorreta(client):
    """Testa o envio (POST) de formulário com dados errados"""
    resposta = client.post('/admin/login', data={
        'login': 'admin',
        'senha': 'senha_errada_aqui'
    }, follow_redirects=True) # Segue o redirecionamento caso o Flask recarregue a página
    
    # A página deve carregar, mas não deve autorizar a entrada
    assert resposta.status_code == 200
    # Verifique se alguma destas palavras aparece no seu HTML quando erra a senha
    # assert b"Incorret" in resposta.data ou b"Inválid" in resposta.data

def test_login_sucesso_com_credenciais_corretas(client):
    """Testa o envio (POST) de formulário com o usuário criado na fixture"""
    resposta = client.post('/admin/login', data={
        'login': 'admin',
        'senha': 'senha_segura_123'
    }, follow_redirects=True)
    
    # Se logou com sucesso, deve redirecionar para o painel administrativo
    assert resposta.status_code == 200
    # Valida se ele carregou elementos da página restrita (ex: botão de sair ou boas vindas)
    assert b"Sair" in resposta.data or b"Admin Teste" in resposta.data

def test_acesso_negado_sem_estar_logado(client):
    """Testa se a aplicação bloqueia intrusos tentando acessar rotas fechadas"""
    # Tenta acessar uma rota que deveria ser protegida (ajuste para a sua rota real)
    resposta = client.get('/admin/dashboard', follow_redirects=True)
    
    # Como não fizemos POST de login neste teste, ele deve nos chutar de volta para a tela de login
    assert b"Acesso Restrito" in resposta.data or b"Login" in resposta.data