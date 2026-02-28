import os
# Avisa o sistema que estamos em modo de teste ANTES de carregar a aplicação
os.environ['AMBIENTE_DE_TESTE'] = 'True'

import pytest
from app import app, db, Ente, Secretaria

@pytest.fixture
def client():
    # Configura o Flask para modo de teste e usa um banco em memória
    app.config['TESTING'] = True
    #app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['WTF_CSRF_ENABLED'] = False

    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            
            # Cria dados básicos simulados para a tela carregar sem erro
            ente_teste = Ente(nome="Prefeitura Teste")
            sec_teste = Secretaria(nome="Secretaria de Teste")
            db.session.add(ente_teste)
            db.session.add(sec_teste)
            db.session.commit()
            
            yield client
            
            db.session.remove()
            db.drop_all()

def test_home_page_carrega_com_sucesso(client):
    """Testa se a página pública (Portal) está online (Status 200)"""
    resposta = client.get('/')
    assert resposta.status_code == 200
    assert b"PCA" in resposta.data # Verifica se a sigla aparece no HTML

def test_login_page_carrega_com_sucesso(client):
    """Testa se a tela de login administrativo está acessível"""
    resposta = client.get('/admin/login')
    assert resposta.status_code == 200
    assert b"Acesso Restrito" in resposta.data