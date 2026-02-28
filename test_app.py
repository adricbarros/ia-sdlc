import os
# Avisa o sistema que estamos em modo de teste ANTES de carregar a aplicação
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from datetime import date
from werkzeug.security import generate_password_hash
from app import app, db, Ente, Secretaria, Usuario, Contratacao, formatar_moeda

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
            
            # 2. Cria o usuário Admin
            senha_hasheada = generate_password_hash("senha_segura_123")
            usuario_teste = Usuario(
                nome="Admin Teste", 
                login="admin", 
                email="admin@teste.com", 
                senha=senha_hasheada,
                secretaria_id=sec_teste.id
            )
            
            # 3. Cria uma Contratação prévia
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

# --- BLOCO 4: TESTES DE EXPORTAÇÃO ---

def test_exportar_excel_com_sucesso(client):
    resposta = client.get('/exportar/excel')
    assert resposta.status_code == 200
    assert resposta.headers['Content-Type'] == 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'

def test_exportar_pdf_com_sucesso(client):
    resposta = client.get('/exportar/pdf')
    assert resposta.status_code == 200

# --- BLOCO 5: GESTÃO DE SECRETARIAS E USUÁRIOS (BÁSICO) ---

def test_cadastrar_nova_secretaria(client):
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.post('/admin/cadastrar/secretaria', data={'nome': 'Secretaria de Saúde'}, follow_redirects=True)
    assert resposta.status_code == 200

def test_listar_usuarios(client):
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
    assert b"Acesso Restrito" in resposta.data or b"Login" in resposta.data

# =========================================================================
# NOVOS TESTES ADICIONADOS PARA ELEVAR A COBERTURA A > 80%
# =========================================================================

# --- BLOCO 7: CAMINHOS TRISTES E VALIDAÇÕES (SAD PATHS) ---

def test_cadastrar_usuario_senhas_diferentes(client):
    """Testa se o sistema barra a criação de usuário quando a confirmação de senha falha"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    dados = {'nome': 'Falha', 'login': 'falha', 'senha': '123', 'confirma_senha': '321', 'email': 'x@x.com', 'secretaria_id': '1'}
    resposta = client.post('/admin/cadastrar/usuario', data=dados, follow_redirects=True)
    assert b"nao conferem" in resposta.data or b"n\xc3\xa3o conferem" in resposta.data

def test_cadastrar_secretaria_duplicada(client):
    """Testa se o sistema impede duas secretarias com o mesmo nome"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    client.post('/admin/cadastrar/secretaria', data={'nome': 'Secretaria de Obras'}, follow_redirects=True)
    # Tenta cadastrar de novo
    resposta = client.post('/admin/cadastrar/secretaria', data={'nome': 'Secretaria de Obras'}, follow_redirects=True)
    assert b"ja esta cadastrada" in resposta.data or b"j\xc3\xa1 est\xc3\xa1 cadastrada" in resposta.data

def test_acesso_negado_usuario_comum_em_rota_admin(client):
    """Testa o RBAC: Garante que um usuário comum não acesse a tela de Secretarias"""
    with app.app_context():
        comum = Usuario(nome="Comum", login="comum", email="c@c.com", senha=generate_password_hash("123"), secretaria_id=1)
        db.session.add(comum)
        db.session.commit()
    
    client.post('/admin/login', data={'login': 'comum', 'senha': '123'}, follow_redirects=True)
    resposta = client.get('/admin/secretarias', follow_redirects=True)
    # Deve ser ejetado para o dashboard com mensagem de erro
    assert b"Acesso Negado" in resposta.data

# --- BLOCO 8: CRUD DE CONTRATAÇÕES (EDITAR E EXCLUIR) ---

def test_editar_contratacao_com_sucesso(client):
    """Testa a edição de um item do PCA"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    dados = {
        'exercicio': '2027', 'objeto': 'Notebooks Atualizados', 'descricao': 'TI',
        'valor': 'R$ 6.000,00', 'dotacao': '321', 'data': '2027-01-01', 'secretaria_id': '1'
    }
    # O item 1 foi criado na nossa Fixture inicial
    resposta = client.post('/admin/editar/contratacao/1', data=dados, follow_redirects=True)
    assert resposta.status_code == 200
    
    with app.app_context():
        item = Contratacao.query.get(1)
        assert item.exercicio == 2027
        assert item.valor_estimado == 6000.0

def test_excluir_contratacao_com_sucesso(client):
    """Testa a exclusão de um item do PCA"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    resposta = client.post('/admin/excluir/contratacao/1', follow_redirects=True)
    assert b"excluida com sucesso" in resposta.data or b"exclu\xc3\xadda com sucesso" in resposta.data

# --- BLOCO 9: RECUPERAÇÃO DE SENHA E CONFIGURAÇÕES DO ENTE ---

def test_esqueci_senha_envio_email(client):
    """Testa a rota de esqueci a senha. (O Flask-Mail não envia e-mails reais no modo TESTING=True)"""
    resposta = client.post('/admin/esqueci-senha', data={'email': 'admin@teste.com'}, follow_redirects=True)
    # Mesmo se der sucesso, a mensagem genérica de segurança é mostrada
    assert b"link de recuperacao" in resposta.data or b"link de recupera\xc3\xa7\xc3\xa3o" in resposta.data

def test_salvar_configuracoes_ente(client):
    """Testa a edição dos dados gerais da Prefeitura"""
    client.post('/admin/login', data={'login': 'admin', 'senha': 'senha_segura_123'}, follow_redirects=True)
    dados_ente = {
        'nome': 'Prefeitura Municipal do Futuro',
        'endereco': 'Rua Inovação, 100',
        'telefone': '9999-9999',
        'email': 'contato@futuro.gov.br'
    }
    resposta = client.post('/admin/configuracoes', data=dados_ente, follow_redirects=True)
    assert b"atualizadas com sucesso" in resposta.data

# --- BLOCO 10: TESTES UNITÁRIOS DIRETOS ---

def test_filtro_moeda_br():
    """Testa a função customizada de formatação de moeda isoladamente"""
    assert formatar_moeda(None) == "0,00"
    assert formatar_moeda(1500.50) == "1.500,50"
    assert formatar_moeda(1000000.00) == "1.000.000,00"