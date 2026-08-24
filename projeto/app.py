from datetime import datetime
from functools import wraps
import os
import time
import sqlite3
import uuid
from flask import (
    Flask,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    session,
)
import qrcode

import criar_banco

app = Flask(__name__)
app.secret_key = "segredo"


def conectar():
    caminho = os.path.join(os.path.dirname(__file__), "escola.db")
    return sqlite3.connect(caminho)


def criar_gestor_padrao():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM professores WHERE funcao = 'gestor'")
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO professores (nome, email, senha, disciplina, funcao)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("Administrador Gestor", "gestor@escola.com", "123", "Gestão", "gestor")
        )
        conn.commit()
        print("✅ Gestor padrão criado com sucesso! (Email: gestor@escola.com / Senha: 123)")
    conn.close()


def verificar_e_resetar_diario():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute("SELECT MAX(data_registro) FROM registros_almoco")
    resultado = cursor.fetchone()

    if resultado and resultado[0]:
        ultima_data_str = resultado[0]
        try:
            data_ultimo_registro = datetime.strptime(
                ultima_data_str.split(".")[0], "%Y-%m-%d %H:%M:%S"
            ).date()
            hoje = datetime.now().date()

            if data_ultimo_registro < hoje:
                cursor.execute(
                    "UPDATE alunos SET almocou = 0, opcao_almoco = 'nao_informado'"
                )
                conn.commit()
        except Exception as e:
            print(f"Erro ao processar verificação de data: {e}")

    conn.close()


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/")
        return f(*args, **kwargs)

    return decorated_function


def tipo_required(*tipos_permitidos):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if session.get("tipo") not in tipos_permitidos:
                return "Acesso negado", 403
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# 🔐 LOGIN / CADASTRO
@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "login":
            email = request.form["email"].strip()
            senha = request.form["senha"].strip()

            conn = conectar()
            cursor = conn.cursor()

            # Tenta logar em professores/gestores
            cursor.execute(
                """
                SELECT id, nome, email, disciplina, funcao 
                FROM professores 
                WHERE email = ? AND senha = ?
            """,
                (email, senha),
            )
            usuario_staff = cursor.fetchone()

            if usuario_staff:
                session.clear()
                session["user_id"] = usuario_staff[0]
                session["user_nome"] = usuario_staff[1]
                session["user_email"] = usuario_staff[2]
                session["user_disciplina"] = usuario_staff[3]
                tipo_user = usuario_staff[4] if len(usuario_staff) > 4 else "professor"
                session["tipo"] = tipo_user
                conn.close()

                if tipo_user == "gestor":
                    return redirect("/painel_gestor")
                return redirect("/status_aluno")

            # Tenta logar como aluno
            cursor.execute(
                """
                SELECT id, nome, curso, almocou 
                FROM alunos 
                WHERE email = ? AND senha = ?
            """,
                (email, senha),
            )
            aluno = cursor.fetchone()
            conn.close()

            if aluno:
                session.clear()
                session["user_id"] = aluno[0]
                session["user_nome"] = aluno[1]
                session["user_curso"] = aluno[2]
                session["tipo"] = "aluno"
                return redirect("/status_aluno")
            else:
                return render_template(
                    "login.html", erro="Email ou senha incorretos!"
                )

        elif acao == "cadastrar":
            nome = request.form["nome"].strip()
            email = request.form["email"].strip()
            tipo = request.form["tipo"]
            senha = request.form["senha"].strip()
            confirmar_senha = request.form["confirmar_senha"].strip()

            if tipo == "gestor":
                return render_template("login.html", erro="Cadastro de gestores não é permitido por esta via.")

            if senha != confirmar_senha:
                return render_template("login.html", erro="Senhas não conferem!")

            if len(senha) < 3:
                return render_template(
                    "login.html", erro="Senha deve ter no mínimo 3 caracteres!"
                )

            conn = conectar()
            cursor = conn.cursor()

            cursor.execute(
                "SELECT id FROM professores WHERE email = ?", (email,)
            )
            if cursor.fetchone():
                conn.close()
                return render_template("login.html", erro="Email já cadastrado!")

            cursor.execute("SELECT id FROM alunos WHERE email = ?", (email,))
            if cursor.fetchone():
                conn.close()
                return render_template("login.html", erro="Email já cadastrado!")

            if tipo == "aluno":
                curso = request.form.get("curso", "").strip()
                if not curso:
                    conn.close()
                    return render_template(
                        "login.html", erro="Curso é obrigatório para alunos!"
                    )

                codigo_qr = f"ALUNO_{uuid.uuid4().hex[:8].upper()}"
                cursor.execute(
                    """
                    INSERT INTO alunos (nome, email, curso, senha, codigo_qr, opcao_almoco, almocou)
                    VALUES (?, ?, ?, ?, ?, 'nao_informado', 0)
                """,
                    (nome, email, curso, senha, codigo_qr),
                )
            else:
                disciplina = request.form.get("disciplina", "").strip()
                cursor.execute(
                    """
                    INSERT INTO professores (nome, email, senha, disciplina, funcao)
                    VALUES (?, ?, ?, ?, 'professor')
                """,
                    (nome, email, senha, disciplina),
                )

            conn.commit()
            conn.close()

            return render_template(
                "login.html", sucesso="✅ Cadastro realizado! Faça login."
            )

    return render_template("login.html")


# 📱 TELA ÚNICA DE STATUS
@app.route("/status_aluno")
@login_required
@tipo_required("aluno", "professor")
def status_aluno():
    verificar_e_resetar_diario()

    user_id = session["user_id"]
    user_nome = session["user_nome"]
    tipo = session["tipo"]

    conn = conectar()
    cursor = conn.cursor()

    if tipo == "aluno":
        user_info = session.get("user_curso", "Aluno")
        cursor.execute(
            "SELECT almocou, opcao_almoco FROM alunos WHERE id = ?", (user_id,)
        )
        resultado = cursor.fetchone()
        almocou = resultado[0] if resultado else 0
        opcao_almoco = resultado[1] if resultado else "nao_informado"
    else:
        user_info = session.get("user_disciplina", "Professor")
        # 🔍 Verifica no banco se o professor registrou almoço HOJE
        cursor.execute(
            """
            SELECT COUNT(*) FROM registros_almoco 
            WHERE professor_id = ? AND DATE(data_registro) = DATE('now', 'localtime')
            """,
            (user_id,),
        )
        resultado = cursor.fetchone()
        almocou = 1 if (resultado and resultado[0] > 0) else 0
        opcao_almoco = "escola" if almocou else "nao_informado"

    conn.close()

    pasta = os.path.join("static", "qrcodes")
    os.makedirs(pasta, exist_ok=True)

    caminho_qr = os.path.join(pasta, f"{tipo}_{user_id}.png")
    caminho_relativo = f"static/qrcodes/{tipo}_{user_id}.png?v={int(time.time())}"

    qr_data = f"{tipo}|{user_id}|{user_nome}|{user_info}"
    qr = qrcode.make(qr_data)
    qr.save(caminho_qr)

    resp = make_response(
        render_template(
            "status_aluno.html",
            nome=user_nome,
            curso=user_info,
            almocou=almocou,
            opcao_almoco=opcao_almoco,
            qr=caminho_relativo,
        )
    )
    resp.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# 🔄 CONFIRMAR ALMOÇO (Ação pelo Botão Manual)
@app.route("/confirmar_almoco", methods=["POST"])
@login_required
def confirmar_almoco():
    user_id = session.get("user_id")
    tipo = session.get("tipo")

    if user_id:
        conn = conectar()
        cursor = conn.cursor()
        try:
            if tipo == "aluno":
                cursor.execute(
                    "UPDATE alunos SET almocou = 1, opcao_almoco = 'escola' WHERE id = ?",
                    (user_id,),
                )
                cursor.execute(
                    "INSERT INTO registros_almoco (aluno_id) VALUES (?)",
                    (user_id,),
                )
            elif tipo == "professor":
                cursor.execute(
                    "INSERT INTO registros_almoco (professor_id) VALUES (?)",
                    (user_id,),
                )

            conn.commit()
        except Exception as e:
            conn.rollback()
            print(f"Erro ao confirmar presença manual: {e}")
        finally:
            conn.close()

    return redirect("/status_aluno")

@app.route("/painel_gestor", methods=["GET", "POST"])
@login_required
def painel_gestor():
    conn = conectar()
    cursor = conn.cursor()

    if request.method == "POST":
        # Processa o cadastro ou a liberação manual do aluno
        acao = request.form.get("acao")

        if acao == "cadastrar_aluno":
            nome = request.form.get("nome")
            email = request.form.get("email")
            curso = request.form.get("curso")
            # Insere no banco...
            cursor.execute(
                "INSERT INTO alunos (nome, email, curso, almocou) VALUES (?, ?, ?, 0)",
                (nome, email, curso),
            )
            conn.commit()

        elif acao == "liberar_manual":
            aluno_id = request.form.get("aluno_id")
            cursor.execute(
                "UPDATE alunos SET almocou = 1 WHERE id = ?", (aluno_id,)
            )
            conn.commit()

        conn.close()
        # 🚀 O REDIRECT Força a atualização da tela com a nova lista do banco
        return redirect(url_for("painel_gestor"))

    # Busca a lista atualizada
    cursor.execute("SELECT id, nome, curso, almocou FROM alunos")
    alunos = cursor.fetchall()
    conn.close()

    return render_template("painel_gestor.html", alunos=alunos)

# 📷 ESCANEAR QR CODE (Apenas Gestor)
@app.route("/escanear_qr")
@login_required
@tipo_required("gestor")
def escanear_qr():
    return render_template("escanear_qr.html")


# 🔳 REGISTRAR QR CODE (Apenas Gestor)
@app.route("/registrar_almoco", methods=["POST"])
@login_required
@tipo_required("gestor")
def registrar_almoco():
    data = request.get_json()
    qr_data = data.get("codigo", "")
    
    print(f"\n[LEITURA QR CODE] Conteudo Lido: '{qr_data}'\n")

    professor_id = session.get("user_id")

    try:
        partes = qr_data.split("|")
        if len(partes) == 4:
            tipo, usuario_id, nome, info = partes[0], int(partes[1]), partes[2], partes[3]
        elif len(partes) == 3:
            nome, info, usuario_id = partes[0], partes[1], int(partes[2])
            tipo = "aluno"
        else:
            return jsonify({"mensagem": "❌ QR Code em formato inválido!", "cor": "vermelho"}), 400
            
    except Exception as e:
        print(f"Erro ao processar QR: {e}")
        return jsonify({"mensagem": "❌ Erro ao processar dados do QR Code!", "cor": "vermelho"}), 400

    conn = conectar()
    cursor = conn.cursor()

    try:
        if tipo == "professor":
            cursor.execute("SELECT id, nome FROM professores WHERE id = ? AND nome = ?", (usuario_id, nome))
            prof = cursor.fetchone()
            
            if prof:
                # Insere o registro de almoço do professor no banco
                cursor.execute(
                    "INSERT INTO registros_almoco (professor_id) VALUES (?)",
                    (prof[0],)
                )
                conn.commit()
                mensagem = f"✅ Professora(o) {prof[1]} liberada(o)!"
                cor = "verde"
            else:
                mensagem = f"❌ Professor(a) {nome} não encontrado!"
                cor = "vermelho"

        else:
            cursor.execute("SELECT id, nome, curso, almocou FROM alunos WHERE id = ? AND nome = ?", (usuario_id, nome))
            aluno = cursor.fetchone()

            if not aluno:
                cursor.execute("SELECT id, nome, curso, almocou FROM alunos WHERE nome = ? AND curso = ?", (nome, info))
                aluno = cursor.fetchone()

            if aluno:
                if aluno[3] == 1:
                    mensagem = f"⚠️ {aluno[1]} ({aluno[2]}) já almoçou hoje!"
                    cor = "amarelo"
                else:
                    cursor.execute(
                        "UPDATE alunos SET almocou = 1, opcao_almoco = 'escola' WHERE id = ?",
                        (aluno[0],),
                    )
                    cursor.execute(
                        "INSERT INTO registros_almoco (aluno_id, professor_id) VALUES (?, ?)",
                        (aluno[0], professor_id),
                    )
                    conn.commit()
                    mensagem = f"✅ Aluno {aluno[1]} ({aluno[2]}) liberado!"
                    cor = "verde"
            else:
                mensagem = f"❌ Aluno {nome} não encontrado!"
                cor = "vermelho"

    except Exception as e:
        conn.rollback()
        print(f"Erro na transação com o banco: {e}")
        mensagem = "❌ Erro de gravação no banco de dados!"
        cor = "vermelho"
    finally:
        conn.close()

    return jsonify({"mensagem": mensagem, "cor": cor})

# 🔄 CHECAGEM EM TEMPO REAL PARA A TELA DO ALUNO/PROFESSOR
@app.route("/api/checar_status")
@login_required
def checar_status():
    user_id = session.get("user_id")
    tipo = session.get("tipo")

    if not user_id:
        return jsonify({"almocou": 0})

    conn = conectar()
    cursor = conn.cursor()

    if tipo == "aluno":
        cursor.execute("SELECT almocou FROM alunos WHERE id = ?", (user_id,))
        res = cursor.fetchone()
        almocou = res[0] if res else 0
    else:
        # Verifica se o professor teve registro hoje
        cursor.execute(
            """
            SELECT COUNT(*) FROM registros_almoco 
            WHERE professor_id = ? AND DATE(data_registro) = DATE('now', 'localtime')
            """,
            (user_id,),
        )
        res = cursor.fetchone()
        almocou = 1 if (res and res[0] > 0) else 0

    conn.close()
    return jsonify({"almocou": almocou})

# 📊 RELATÓRIO (Apenas Gestor)
@app.route("/relatorio")
@login_required
@tipo_required("gestor")
def relatorio():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT curso, 
               COUNT(*) as total,
               SUM(CASE WHEN opcao_almoco = 'escola' THEN 1 ELSE 0 END) as preferem_escola,
               SUM(CASE WHEN opcao_almoco = 'externo' THEN 1 ELSE 0 END) as preferem_externo,
               SUM(almocou) as almoçaram
        FROM alunos 
        GROUP BY curso
    """)
    estatisticas = cursor.fetchall()

    conn.close()
    return render_template("relatorio.html", estatisticas=estatisticas)


# 🗑️ RESETAR ALMOÇO (Apenas Gestor)
@app.route("/resetar_almoco", methods=["POST"])
@login_required
@tipo_required("gestor")
def resetar_almoco():
    conn = conectar()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE alunos SET almocou = 0, opcao_almoco = 'nao_informado'"
    )
    conn.commit()
    conn.close()
    return redirect("/painel_gestor")


# 🚪 LOGOUT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


if __name__ == '__main__':
    criar_gestor_padrao()
    # Abre o servidor Flask aceitando conexões da rede local (host="0.0.0.0")
    app.run(host="0.0.0.0", port=5000, debug=True)