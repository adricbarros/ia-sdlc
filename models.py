import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import event # <-- IMPORTANTE ADICIONAR ISSO

db = SQLAlchemy()

class Secretaria(db.Model):
    __tablename__ = 'secretarias'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(255), nullable=False, unique=True)
    contratacoes = db.relationship('Contratacao', back_populates='secretaria')
    usuarios = db.relationship('Usuario', back_populates='secretaria')

class Usuario(db.Model):
    __tablename__ = 'usuarios'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome = db.Column(db.String(255), nullable=False)
    login = db.Column(db.String(100), unique=True, nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=True)
    senha = db.Column(db.String(255), nullable=False)
    secretaria_id = db.Column(db.Integer, db.ForeignKey('secretarias.id'), nullable=False)
    secretaria = db.relationship('Secretaria', back_populates='usuarios')
    
    def set_password(self, password):
        self.senha = generate_password_hash(password)
    def check_password(self, password):
        return check_password_hash(self.senha, password)

class Contratacao(db.Model):
    __tablename__ = 'contratacoes'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    exercicio = db.Column(db.Integer, nullable=False)
    objeto = db.Column(db.String(500), nullable=False)
    descricao = db.Column(db.Text)
    valor_estimado = db.Column(db.Float)
    dotacao = db.Column(db.String(100))
    data_planejada = db.Column(db.Date)
    secretaria_id = db.Column(db.Integer, db.ForeignKey('secretarias.id'), nullable=False)
    data_atualizacao = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    
    # A coluna agora é normal e permite nulo inicialmente (pois será preenchida logo após o insert)
    codigo_identificador = db.Column(db.String(100), unique=True, nullable=True)
    
    secretaria = db.relationship('Secretaria', back_populates='contratacoes')

class Ente(db.Model):
    __tablename__ = 'ente'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, default="Prefeitura Municipal Modelo")
    endereco = db.Column(db.String(255), default="Praça Central, S/N - Centro")
    telefone = db.Column(db.String(50), default="(00) 0000-0000")
    email = db.Column(db.String(100), default="contato@modelo.gov.br")
    logo_path = db.Column(db.String(255), nullable=True) # Caminho da imagem salva

# =====================================================================
# EVENT HOOK: Para corrigir o erro da Computed Column
# =====================================================================
@event.listens_for(Contratacao, 'after_insert')
def gerar_codigo_apos_insert(mapper, connection, target):
    """
    Este evento é acionado pelo SQLAlchemy IMEDIATAMENTE após a linha ser inserida
    no banco de dados, ou seja, AGORA nós já temos o 'id' verdadeiro (target.id).
    """
    codigo = f"PCA-{target.id}.{target.exercicio}-{target.secretaria_id}"
    
    # Atualiza o próprio registro recém-criado com o código formatado
    connection.execute(
        Contratacao.__table__.update().
        where(Contratacao.id == target.id).
        values(codigo_identificador=codigo)
    )