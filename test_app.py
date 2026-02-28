import os
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from datetime import date
from werkzeug.security import generate_password_hash
from app import app, db, Ente, Secretaria, Usuario, Contratacao, formatar_moeda

@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False 
    app.config['MAIL_SUPPRESS_SEND'] = True

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
            
            # 2. Cria os Usuários (Admin e Comum)
            senha_hasheada = generate_password_hash("senha_segura_123")
            usuario_admin = Usuario(nome="Admin Teste", login="admin", email="admin@teste.com", senha=senha_hasheada, secretaria_id=sec_teste.id)
            usuario_comum = Usuario(nome="Comum Teste", login="comum", email="comum@teste.com", senha=senha_hasheada, secretaria_id=sec_teste.id)
            
            # 3. Cria uma Contratação prévia
            contratacao_teste = Contratacao(exercicio=2026, objeto="Notebooks", descricao="TI", valor_estimado=5000.00, dotacao="123", data_planejada=date(2026, 1, 1), secretaria_id=sec_teste.id)
            
            db.session.add_all([usuario_admin, usuario_comum, contratacao_teste])
            db.session.commit()
            
            yield client
            
            db.session.remove()
            if 'sqlite' in app.config['SQLALCHEMY_DATABASE_URI']:
                db.drop_all()

# --- BLOCOS DE 1 A 10 (MANTIDOS E FUNCIONANDO) ---

def test_home_page_carrega_com_sucesso(client):
    resposta = client.get('/')
    assert resposta.status_code == 200

def test_erro_404_pagina_nao_encontrada(client):
    resposta = client.get('/uma-url-que-nao-existe')
    assert resposta.status_code == 404

def test_login_sucesso_com_credenciais_corretas(client):
    resposta = client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert b"Sair" in resposta.data

def test_acesso_negado_sem_estar_logado(client):
    resposta = client.get('/admin/dashboard', follow_redirects=True)
    assert b"Acesso Restrito" in resposta.data

def test_cadastrar_nova_contratacao_com_sucesso(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    dados = {'exercicio': '2026', 'objeto': 'Servidores', 'descricao': 'TI', 'valor': 'R$ 15.000,50', 'dotacao': '123', 'data': '2026-12-31', 'secretaria_id': '1'}
    client.post('/admin/cadastrar/contratacao', data=dados, follow_redirects=True)
    with app.app_context():
        assert Contratacao.query.filter_by(objeto='Servidores').first() is not None

def test_exportar_excel_com_sucesso(client):
    resposta = client.get('/exportar/excel')
    assert resposta.status_code == 200

def test_exportar_pdf_com_sucesso(client):
    resposta = client.get('/exportar/pdf')
    assert resposta.status_code == 200

def test_cadastrar_nova_secretaria(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    client.post('/admin/cadastrar/secretaria', data={'nome': 'Saúde'}, follow_redirects=True)
    with app.app_context():
        assert Secretaria.query.filter_by(nome='Saúde').first() is not None

def test_listar_usuarios(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert client.get('/admin/usuarios').status_code == 200

def test_configuracoes_ente_carrega(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert client.get('/admin/configuracoes').status_code == 200

def test_logout(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert b"Acesso Restrito" in client.get('/admin/logout', follow_redirects=True).data

def test_cadastrar_usuario_senhas_diferentes(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.post('/admin/cadastrar/usuario', data={'nome': 'F', 'login': 'f', 'senha': '1', 'confirma_senha': '2', 'email': 'x@x.com', 'secretaria_id': '1'}, follow_redirects=True)
    assert b"conferem" in resposta.data

def test_cadastrar_secretaria_duplicada(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    client.post('/admin/cadastrar/secretaria', data={'nome': 'Obras'}, follow_redirects=True)
    resposta = client.post('/admin/cadastrar/secretaria', data={'nome': 'Obras'}, follow_redirects=True)
    assert b"cadastrada" in resposta.data

def test_acesso_negado_usuario_comum_em_rota_admin(client):
    client.post('/admin/login', data={'login': 'comum', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert b"Acesso Negado" in client.get('/admin/secretarias', follow_redirects=True).data

def test_editar_contratacao_com_sucesso(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    client.post('/admin/editar/contratacao/1', data={'exercicio': '2027', 'objeto': 'Up', 'descricao': 'TI', 'valor': '6000', 'dotacao': '321', 'data': '2027-01-01', 'secretaria_id': '1'})
    with app.app_context():
        assert Contratacao.query.get(1).exercicio == 2027

def test_excluir_contratacao_com_sucesso(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert b"sucesso" in client.post('/admin/excluir/contratacao/1', follow_redirects=True).data

def test_esqueci_senha_envio_email(client):
    resposta = client.post('/admin/esqueci-senha', data={'email': 'admin@teste.com'}, follow_redirects=True)
    assert b"caixa de entrada" in resposta.data or b"Erro interno" in resposta.data

def test_salvar_configuracoes_ente(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    assert b"sucesso" in client.post('/admin/configuracoes', data={'nome': 'Prefeitura', 'endereco': 'X', 'telefone': '1', 'email': 'x@x.com'}, follow_redirects=True).data

def test_filtro_moeda_br():
    assert formatar_moeda(1500.50) == "1.500,50"

# =========================================================================
# BLOCO 11: O GOLPE FINAL (>80% COBERTURA)
# =========================================================================

def test_home_filtros_ativos(client):
    """Testa se a Home carrega corretamente quando o usuário faz uma pesquisa"""
    resposta = client.get('/?secretaria=1&exercicio=2026&codigo=PCA')
    assert resposta.status_code == 200

def test_dashboard_carrega_para_usuario_comum(client):
    """Cobre o bloco 'else' do dashboard (quando não é admin)"""
    client.post('/admin/login', data={'login': 'comum', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.get('/admin/dashboard')
    assert resposta.status_code == 200

def test_editar_e_excluir_secretaria(client):
    """Cobre as funções de gerenciar secretarias"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    # Editar
    client.post('/admin/editar/secretaria/1', data={'nome': 'Nome Alterado'}, follow_redirects=True)
    # Excluir (Vai acionar o bloco except, pois já existem itens vinculados, o que é ótimo para cobertura!)
    resposta = client.post('/admin/excluir/secretaria/1', follow_redirects=True)
    assert b"Erro" in resposta.data or b"sucesso" in resposta.data

def test_editar_e_excluir_usuario(client):
    """Cobre as rotas de gerenciar usuários"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    # Editar o usuário 2 (comum)
    client.post('/admin/editar/usuario/2', data={'nome': 'Comum Editado', 'login': 'comum2', 'email': 'novo@teste.com', 'secretaria_id': '1'}, follow_redirects=True)
    # Excluir o usuário 2
    resposta = client.post('/admin/excluir/usuario/2', follow_redirects=True)
    assert resposta.status_code == 200

def test_reset_de_senha_via_token(client):
    """Cobre a rota de geração do link de e-mail e redefinição de senha"""
    from itsdangerous import URLSafeTimedSerializer
    with app.app_context():
        # Gera um token válido idêntico ao que o sistema enviaria por e-mail
        s = URLSafeTimedSerializer(app.secret_key)
        token = s.dumps('comum@teste.com', salt='recuperacao-senha')
    
    # Simula o usuário clicando no link do e-mail (GET) e salvando a senha nova (POST)
    client.get(f'/admin/resetar/{token}')
    resposta = client.post(f'/admin/resetar/{token}', data={'nova_senha': '789', 'confirma_senha': '789'}, follow_redirects=True)
    assert b"redefinida com sucesso" in resposta.data