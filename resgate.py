# Script para resetar a senha do usuário admin para "admin123"
from app import app, db
from models import Usuario # ou de onde você importa a classe Usuario

with app.app_context():
    admin = Usuario.query.filter_by(login='admin').first()
    if admin:
        admin.set_password('admin123') # Define a senha de volta para admin123
        db.session.commit()
        print("✅ SUCESSO! A senha do admin foi resetada para: admin123")
    else:
        print("❌ ERRO: Usuário 'admin' não encontrado no banco.")