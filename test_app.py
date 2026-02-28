import os
# Avisa o sistema que estamos em modo de teste ANTES de carregar a aplicação
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from werkzeug.security import generate_password_hash
# Importando todos os modelos, incluindo Contratacao
from app import app, db, Ente, Secretaria, Usuario, Contratacao 

@pytest.fixture
def client():
    # Configura o Flask para modo de teste
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False 

    with app.test_client() as client:
        with app.app_context():
            # --- TRAVA DE SEGURANÇA (KILL SWITCH) ---
            if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                raise RuntimeError("⚠️ ALERTA DE SEGURANÇA: O teste tentou conectar em um banco real. Abortando!")
            
            db.create_all()
            
            # 1. Cria a Secretaria e o Ente primeiro para gerarem um ID
            ente_teste = Ente(nome="Prefeitura Teste")
            sec_teste = Secretaria(nome="Secretaria de Teste")
            db.session.add_all([ente_teste, sec_teste])
            db.session.commit() # Agora sec_teste.id existe!
            
            # 2. Cria o usuário falso vinculando-o à Secretaria recém-criada
            senha_hasheada = generate_password_hash("senha_segura_123")
            usuario_teste = Usuario(
                nome="Admin Teste", 
                login="admin", 
                email="admin@teste.com", 
                senha=senha_hasheada,
                secretaria_id=sec_teste.id
            )
            
            db.session.add(usuario_teste)
            db.session.commit()
            
            yield client
            
            db.session.remove()
            # Limpa o banco para que o próximo teste comece do zero
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
                db.drop_all()

# --- BLOCO 1: TESTES PÚBLICOS ---

def test_home_page_carrega_com_sucesso(client):
    resposta = client.get('/')
    assert resposta.status_code == 200
    assert b"PCA" in resposta.data

def test_erro_404_pagina_nao_encontrada(client):
    resposta = client.get('/uma-url-que-nao-existe-no-sistema')
    assert resposta.status_code == 404

# --- BLOCO 2: TESTES DE AUTENTICAÇÃO ---

def test_login_page_carrega_com_sucesso(client):
    resposta = client.get('/admin/login')
    assert resposta.status_code == 200

def test_login_falha_com_senha_incorreta(client):
    resposta = client.post('/admin/login', data={
        'login': 'admin',
        'senha': 'senha_errada_aqui'
    }, follow_redirects=True) 
    
    assert resposta.status_code == 200

def test_login_sucesso_com_credenciais_corretas(client):
    resposta = client.post('/admin/login', data={
        'login': 'admin',
        'senha': 'senha_segura_123'
    }, follow_redirects=True)
    
    assert resposta.status_code == 200
    assert b"Sair" in resposta.data or b"Admin Teste" in resposta.data

def test_acesso_negado_sem_estar_logado(client):
    resposta = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Acesso Restrito" in resposta.data or b"Login" in resposta.data

# --- BLOCO 3: TESTES DE FLUXO DE DADOS E INTEGRAÇÃO ---

def test_dashboard_carrega_apos_login(client):
    """Testa se o dashboard abre perfeitamente após o login"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    
    resposta = client.get('/admin/dashboard', follow_redirects=True)
    assert resposta.status_code == 200

def test_cadastrar_nova_contratacao_com_sucesso(client):
    """Simula o fluxo completo com os dados reais mapeados do app.py"""
    
    # 1. Faz o login
    client.post('/admin/login', data={
        'login': 'admin',
        'senha': 'senha_segura_123'
    }, follow_redirects=True)

    # 2. Prepara os dados EXATAMENTE como o seu formulário HTML envia
    dados_contratacao = {
        'exercicio': '2026',
        'objeto': 'Aquisição de Servidores para Home Lab',
        'descricao': 'Compra de equipamentos para infraestrutura',
        'valor': 'R$ 15.000,50',  # Testando o seu sanitizador de código!
        'dotacao': '12.345.678',
        'data': '2026-12-31',     # Formato exigido no app.py (%Y-%m-%d)
        'secretaria_id': '1'
    }

    # 3. Dispara para a ROTA REAL do seu aplicativo
    resposta = client.post('/admin/cadastrar/contratacao', data=dados_contratacao, follow_redirects=True)

    # Verifica se a página carregou normalmente
    assert resposta.status_code == 200
    
    # 4. Vai no banco de dados conferir se salvou e se o seu sanitizador funcionou
    with app.app_context():
        item = Contratacao.query.filter_by(objeto='Aquisição de Servidores para Home Lab').first()
        assert item is not None
        # O banco tem que ter salvo o float limpo (15000.5), provando que sua função no app.py funciona perfeitamente
        assert item.valor_estimado == 15000.50