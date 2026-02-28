import os
# Avisa o sistema que estamos em modo de teste ANTES de carregar a aplicação
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from datetime import date
from werkzeug.security import generate_password_hash
from app import app, db, Ente, Secretaria, Usuario, Contratacao 

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False 

    with app.test_client() as client:
        with app.app_context():
            # --- TRAVA DE SEGURANÇA (KILL SWITCH) ---
            if 'sqlite' not in app.config['SQLALCHEMY_DATABASE_URI']:
                raise RuntimeError("⚠️ ALERTA DE SEGURANÇA: O teste tentou conectar em um banco real. Abortando!")
            
            db.create_all()
            
            # 1. Cria a Secretaria e o Ente
            ente_teste = Ente(nome="Prefeitura Teste")
            sec_teste = Secretaria(nome="Secretaria de Teste")
            db.session.add_all([ente_teste, sec_teste])
            db.session.commit() 
            
            # 2. Cria o usuário
            senha_hasheada = generate_password_hash("senha_segura_123")
            usuario_teste = Usuario(
                nome="Admin Teste", 
                login="admin", 
                email="admin@teste.com", 
                senha=senha_hasheada,
                secretaria_id=sec_teste.id
            )
            
            # 3. Cria uma Contratação prévia para os testes de Exportação renderizarem o Excel/PDF
            contratacao_teste = Contratacao(
                exercicio=2026,
                objeto="Notebooks para teste",
                descricao="Compra de equipamentos",
                valor_estimado=5000.00,
                dotacao="123",
                data_planejada=date(2026, 1, 1),
                secretaria_id=sec_teste.id
            )
            
            db.session.add_all([usuario_teste, contratacao_teste])
            db.session.commit()
            
            yield client
            
            db.session.remove()
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

def test_login_sucesso_com_credenciais_corretas(client):
    resposta = client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert resposta.status_code == 200
    assert b"Sair" in resposta.data or b"Admin Teste" in resposta.data

def test_acesso_negado_sem_estar_logado(client):
    resposta = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Acesso Restrito" in resposta.data or b"Login" in resposta.data

# --- BLOCO 3: FLUXO DE CONTRATAÇÕES ---

def test_cadastrar_nova_contratacao_com_sucesso(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    dados = {
        'exercicio': '2026', 'objeto': 'Aquisição de Servidores', 'descricao': 'TI',
        'valor': 'R$ 15.000,50', 'dotacao': '123', 'data': '2026-12-31', 'secretaria_id': '1'
    }
    resposta = client.post('/admin/cadastrar/contratacao', data=dados, follow_redirects=True)
    assert resposta.status_code == 200
    
    with app.app_context():
        item = Contratacao.query.filter_by(objeto='Aquisição de Servidores').first()
        assert item is not None

# --- BLOCO 4: TESTES DE EXPORTAÇÃO (O Pulo do Gato para Cobertura) ---

def test_exportar_excel_com_sucesso(client):
    """Testa se o sistema consegue gerar a planilha do Excel usando os dados em memória"""
    resposta = client.get('/exportar/excel')
    assert resposta.status_code == 200
    # Valida se o arquivo baixado é realmente um Excel
    assert resposta.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def test_exportar_pdf_com_sucesso(client):
    """Testa se o sistema consegue renderizar a página que gera o PDF"""
    resposta = client.get('/exportar/pdf')
    assert resposta.status_code == 200

# --- BLOCO 5: GESTÃO DE SECRETARIAS E USUÁRIOS ---

def test_cadastrar_nova_secretaria(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.post('/admin/cadastrar/secretaria', data={'nome': 'Secretaria de Saúde'}, follow_redirects=True)
    assert resposta.status_code == 200
    with app.app_context():
        assert Secretaria.query.filter_by(nome='Secretaria de Saúde').first() is not None

def test_listar_usuarios(client):
    """Testa se a página de usuários carrega sem quebrar"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.get('/admin/usuarios')
    assert resposta.status_code == 200

# --- BLOCO 6: CONFIGURAÇÕES E LOGOUT ---

def test_configuracoes_ente_carrega(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.get('/admin/configuracoes')
    assert resposta.status_code == 200

def test_logout(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.get('/admin/logout', follow_redirects=True)
    # Ao sair, o sistema deve perder a sessão e o botão "Acesso Restrito" volta a aparecer
    assert b"Acesso Restrito" in resposta.data or b"Login" in resposta.data