import sqlite3
import os

caminho = os.path.join(os.path.dirname(__file__), "escola.db")

# Deletar banco antigo
if os.path.exists(caminho):
    os.remove(caminho)
    print("Banco antigo removido!")

conn = sqlite3.connect(caminho)
cursor = conn.cursor()

# ========== TABELA DE ALUNOS (COM EMAIL, QR CODE E OPÇÃO DE ALMOÇO) ==========
cursor.execute("""
CREATE TABLE alunos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    curso TEXT NOT NULL,
    senha TEXT NOT NULL,
    codigo_qr TEXT UNIQUE,
    opcao_almoco TEXT DEFAULT 'nao_informado',
    almocou INTEGER DEFAULT 0,
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ========== TABELA DE PROFESSORES ==========
cursor.execute("""
CREATE TABLE professores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    senha TEXT NOT NULL,
    disciplina TEXT,
    funcao TEXT DEFAULT 'professor',
    data_cadastro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# ========== TABELA DE REGISTROS DE ALMOÇO ==========
cursor.execute("""
CREATE TABLE registros_almoco (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    aluno_id INTEGER,
    professor_id INTEGER,
    data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (aluno_id) REFERENCES alunos(id),
    FOREIGN KEY (professor_id) REFERENCES professores(id)
)
""")

# Inserir alunos de exemplo
alunos_exemplo = [
    ('João Silva', 'joao@email.com', 'Engenharia', '123', 'ALUNO_JOAO_01', 'escola', 0),
    ('Maria Santos', 'maria@email.com', 'Medicina', '123', 'ALUNO_MARIA_02', 'externo', 0),
    ('Pedro Costa', 'pedro@email.com', 'Direito', '123', 'ALUNO_PEDRO_03', 'nao_informado', 0),
    ('Ana Oliveira', 'ana@email.com', 'Arquitetura', '123', 'ALUNO_ANA_04', 'escola', 0),
    ('Carlos Souza', 'carlos@email.com', 'Sistemas', '123', 'ALUNO_CARLOS_05', 'escola', 0)
]

for aluno in alunos_exemplo:
    cursor.execute("""
        INSERT INTO alunos (nome, email, curso, senha, codigo_qr, opcao_almoco, almocou)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, aluno)

# Inserir professores de exemplo
professores_exemplo = [
    ('Prof. Administrador', 'admin@escola.com', 'admin123', 'Administração', 'admin'),
    ('Profa. Carla Lima', 'carla@escola.com', '123', 'Matemática', 'professor'),
    ('Prof. Roberto Alves', 'roberto@escola.com', '123', 'Física', 'professor'),
    ('Profa. Mariana Santos', 'mariana@escola.com', '123', 'Química', 'professor'),
    ('Prof. Paulo Silva', 'paulo@escola.com', '123', 'Português', 'professor')
]

for professor in professores_exemplo:
    cursor.execute("""
        INSERT INTO professores (nome, email, senha, disciplina, funcao)
        VALUES (?, ?, ?, ?, ?)
    """, professor)

conn.commit()
conn.close()

print("=" * 60)
print("✅ BANCO DE DADOS RECRIADO COM SUCESSO!")
print("=" * 60)