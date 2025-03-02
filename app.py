from flask import Flask, request, render_template, url_for, redirect, flash, jsonify, send_file, session
from flask_mysqldb import MySQL
import functools
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
import random, string, MySQLdb
from fpdf import FPDF
import os
from datetime import datetime

app = Flask(__name__)
app.config['MYSQL_HOST'] = 'localhost'  # host de la base de datos
app.config['MYSQL_USER'] = 'root'  # usuario de la base de datos
app.config['MYSQL_PASSWORD'] = ''  # contraseña de la base de datos
app.config['MYSQL_DB'] = 'db_medicos'  # nombre de la base de datos

app.secret_key = 'my_secret'

mysql = MySQL(app)  # se crea una instancia de MySQL

#decorador para verificar si el usuario esta logeado
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session or not session['logged_in']:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

#ruta para verificacion de login
@app.route('/login-entrada', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        rfc = request.form['rfc']
        password = request.form['password']

        try:
            cursor = mysql.connection.cursor()
            cursor.execute("SELECT * FROM medicos WHERE rfc = %s", (rfc,))
            user = cursor.fetchone()
            cursor.close()

            if user:
                stored_password = user[7]
                user_role = user[6]

                if check_password_hash(stored_password, password):
                    session['logged_in'] = True
                    session['user_id'] = user[0]
                    session['nombre_medico'] = user[2]
                    session['rol'] = user_role
                    session['cedula'] = user[3]
                    print(user[3])  # Esto imprimirá el contenido de la fila devuelta por la consulta SQL

                    flash('Inicio de sesión exitoso. ¡Bienvenido!', 'success')
                    return redirect(url_for('Home'))
                else:
                    flash('Credenciales incorrectas', 'danger')
                    return redirect(url_for('login'))
            else:
                flash('Usuario no encontrado', 'danger')
                return redirect(url_for('login'))

        except Exception as e:
            flash('Ocurrió un error durante el inicio de sesión. Por favor, intenta de nuevo.', 'danger')
            return redirect(url_for('login'))

    return render_template('login.html')


#ruta para cerrar sesion
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('user_id', None)
    session.pop('rol', None)
    session.pop('nombre_medico', None)
    session.pop('cedula', None)
    flash('Has cerrado sesión exitosamente.', 'success')
    return redirect(url_for('login'))

#ruta Login
@app.route('/')
def index():
    return render_template('login.html')

#Pagina de inicio de la aplicacion
@app.route('/Home')
@login_required
def Home():
    return render_template('Home.html')

#ruta para registrar un medico nuevo Solo accesible para el administrador
@app.route('/registro')
@login_required
def registro():
    return render_template('registro.html')

#ruta para ver los medicos registrados Solo accesible para el administrador
@app.route('/consulta')
@login_required
def consulta():
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT id, rfc, Nombre, CedulaP, Correo, especialidad, pass, SUBSTR(rol, 1, 8) AS rol FROM medicos')
    medicos = cursor.fetchall()
    cursor.close()
    return render_template('Consulta.html', medicos=medicos)

#ruta para ver los pacientes registrados de un medico en sesion
@app.route('/consultaP')
@login_required
def consultaP():
    medico_id =  session['user_id']
    
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM expedientes WHERE medico = %s', (medico_id,))
    pacientes = cursor.fetchall()
    cursor.close()
    
    return render_template('ConsultaP.html', pacientes=pacientes)

#ruta para guardar el medico
@app.route('/GuardarMedico', methods=['POST'])
@login_required
def guardarMedico():
    if request.method == 'POST':
        frfc = request.form['rfc']
        fnombre = request.form['nombre']
        fcedula = request.form['cedulaP']
        fcorreo = request.form['correo']
        fespecialidad = request.form['especialidad']
        fpass = request.form['pass']
        frol = request.form['rol']

        try:
            cursor = mysql.connection.cursor()

            # Verificar si el RFC ya está registrado
            cursor.execute('SELECT * FROM medicos WHERE rfc = %s', (frfc,))
            existing_user_rfc = cursor.fetchone()

            if existing_user_rfc:
                flash('El RFC ya está registrado. Por favor, usa un RFC diferente.', 'danger')
                return render_template('registro.html', rfc=frfc, nombre=fnombre, cedula=fcedula, correo=fcorreo, especialidad=fespecialidad, rol=frol)

            # Verificar si la cédula ya está registrada
            cursor.execute('SELECT * FROM medicos WHERE CedulaP = %s', (fcedula,))
            existing_user_cedula = cursor.fetchone()

            if existing_user_cedula:
                flash('La cédula profesional ya está registrada. Por favor, usa una cédula diferente.', 'danger')
                return render_template('registro.html', rfc=frfc, nombre=fnombre, cedula=fcedula, correo=fcorreo, especialidad=fespecialidad, rol=frol)

            hashed_password = generate_password_hash(fpass)

            cursor.execute(
                'INSERT INTO medicos (rfc, Nombre, CedulaP, Correo, especialidad, pass, rol) VALUES(%s, %s, %s, %s, %s, %s, %s)',
                (frfc, fnombre, fcedula, fcorreo, fespecialidad, hashed_password, frol)
            )
            mysql.connection.commit()
            cursor.close()

            flash('El médico fue registrado correctamente', 'success')
            return redirect(url_for('consulta'))

        except Exception as e:
            flash(f'Ocurrió un error al registrar el médico: {str(e)}', 'danger')
            return render_template('registro.html', rfc=frfc, nombre=fnombre, cedula=fcedula, correo=fcorreo, especialidad=fespecialidad, rol=frol)


#ruta para editar un registro de medico solo accesible para el administrador
@app.route('/editar/<id>')
@login_required
def editar(id):
    cursor = mysql.connection.cursor()
    cursor.execute('SELECT * FROM medicos WHERE id = %s', [id])
    medicoE = cursor.fetchone()
    return render_template('editar.html', medico=medicoE)

#ruta para actualizar un registro de medico solo accesible para el administrador
@app.route('/ActualizarMedico/<id>', methods=['POST'])
@login_required
def actualizarMedico(id):
    if request.method == 'POST':
        try:
            frfc = request.form['rfc']
            fnombre = request.form['nombre']
            fcedula = request.form['cedula']
            fcorreo = request.form['correo']
            fespecialidad = request.form['especialidad']
            fpass = request.form.get('pass')  # Usa get() para que sea opcional
            frol = request.form['rol']

            cursor = mysql.connection.cursor()

            if fpass:  # Si se proporciona una nueva contraseña
                hashed_password = generate_password_hash(fpass)
                cursor.execute(
                    'UPDATE medicos SET rfc=%s, Nombre=%s, CedulaP=%s, Correo=%s, pass=%s, especialidad=%s, rol=%s WHERE id=%s',
                    (frfc, fnombre, fcedula, fcorreo, hashed_password, fespecialidad, frol, id)
                )
            else:  # Si no se proporciona una nueva contraseña
                cursor.execute(
                    'UPDATE medicos SET rfc=%s, Nombre=%s, CedulaP=%s, Correo=%s, especialidad=%s, rol=%s WHERE id=%s',
                    (frfc, fnombre, fcedula, fcorreo, fespecialidad, frol, id)
                )

            mysql.connection.commit()
            cursor.close()

            flash('Registro actualizado correctamente', 'success')
            return redirect(url_for('consulta'))
        except Exception as e:
            flash('Error al actualizar el registro: ' + str(e), 'danger')
            return redirect(url_for('consulta'))

# se va a tener que actualizar esta funcion  ya que cuando se borre se tendran que borrar todos los registros relacionados con el medico
#Ruta para eliminar un registro
@app.route('/eliminar/<id>')
def eliminar(id):
    # Obtener el id del médico logueado desde la sesión
    medico_logueado_id = session.get('user_id')

    # Verificar si el médico logueado está intentando eliminar su propio registro
    if str(medico_logueado_id) == id:
        flash('No puedes eliminar tu propio registro mientras estás logueado.')
        return redirect(url_for('consulta'))

    try:
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM recetas WHERE id_medico = %s', [id])
        cursor.execute('DELETE FROM pacientes WHERE id_medicos = %s', [id])
        cursor.execute('DELETE FROM exploracion WHERE id_medico = %s', [id])
        cursor.execute('DELETE FROM expedientes WHERE Medico = %s', [id])
        cursor.execute('DELETE FROM medicos WHERE id = %s', [id])
        mysql.connection.commit()
        flash('El medico se eliminó correctamente!')
        return redirect(url_for('consulta'))
    except Exception as e:
        flash('Error al eliminar el registro: ' + str(e))
        return redirect(url_for('consulta'))



#funcion para la template de realizar expedientes
@app.route('/expedientes', methods=['GET'])
@login_required
def mostrar_expediente():
    return render_template('expedientes.html')

# funcion para generar un numero de expediente
def generar_numero_expediente(medico, paciente, fecha_nacimiento):
    medico_iniciales = medico[:2].upper()
    paciente_iniciales = paciente[:2].upper()
    fecha_partes = fecha_nacimiento.split('-')
    mes = fecha_partes[1]
    dia = fecha_partes[2]
    año = fecha_partes[0][-2:]

    letra_random = random.choice(string.ascii_uppercase)
    numero_random = random.randint(0, 9)

    return f"{medico_iniciales}{paciente_iniciales}{mes}{dia}{año}{letra_random}{numero_random}"

# esta es la ruta perra para guardar los expedientes
@app.route('/registrar_expediente', methods=['POST'])
@login_required
def registrar_expediente():
    cursor = mysql.connection.cursor()

    try:
        medico = session['user_id']  # Se obtiene el nombre del médico de la sesión
        nmedico = session['nombre_medico']
        nombre_paciente = request.form['nombre_paciente'].upper()
        fecha_nacimiento = request.form['fecha_nacimiento']
        enfermedades_cronicas = request.form.get('enfermedades_cronicas', None)
        alergias = request.form.get('alergias', None)
        antecedentes_familiares = request.form.get('antecedentes_familiares', None)

        # Generación del número de expediente
        expediente = generar_numero_expediente(nmedico, nombre_paciente, fecha_nacimiento)

        # Verificar si el número de expediente ya existe
        cursor.execute("SELECT COUNT(*) FROM Expedientes WHERE NumeroExpediente = %s", [expediente])
        if cursor.fetchone()[0] > 0:
            flash("El número de expediente ya existe. Intenta de nuevo.", "error")
            return redirect(url_for('expediente_form'))

        # Guardar los datos en la base de datos
        cursor.execute("""
            INSERT INTO Expedientes (Medico, NombrePaciente, FechaNacimiento, EnfermedadesCronicas, Alergias, AntecedentesFamiliares, NumeroExpediente)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (medico, nombre_paciente, fecha_nacimiento, enfermedades_cronicas, alergias, antecedentes_familiares, expediente))
        mysql.connection.commit()

        flash(f"Expediente registrado exitosamente:<br><strong>{nombre_paciente}</strong><br>Número de expediente: {expediente}", "success")
        return redirect(url_for('consultaP'))  # Redirigir a otra página de éxito
    
    

    except MySQLdb.Error as e:
        mysql.connection.rollback()
        flash(f"Ocurrió un error al registrar el expediente: {str(e)}", "error")
        return redirect(url_for('expediente_form'))

    finally:
        cursor.close()
        
#funciones para expedientes 
@app.route('/eliminarExpediente/<id>')
@login_required
def eliminarExpediente(id):
    try:
        cursor = mysql.connection.cursor()
        cursor.execute('DELETE FROM expedientes WHERE ID = %s', [id])
        mysql.connection.commit()
        flash('El expediente se elimino correctamente!')
        return redirect(url_for('consultaP'))
    except Exception as e:
        flash('Error al eliminar el registro' + str(e))
        return redirect(url_for('consultap'))

@app.route('/editarExpe/<id>', methods=['GET', 'POST'])
@login_required
def actualizarExpediente(id):
    try:
        if request.method == 'POST':
            # Recopilar los datos del formulario
            nombre_paciente = request.form['nombre_paciente']
            fecha_nacimiento = request.form['fecha_nacimiento']
            enfermedades_cronicas = request.form.get('enfermedades_cronicas', None)
            alergias = request.form.get('alergias', None)
            antecedentes_familiares = request.form.get('antecedentes_familiares', None)

            cursor = mysql.connection.cursor()
            cursor.execute(
                'UPDATE expedientes SET NombrePaciente=%s, FechaNacimiento=%s, EnfermedadesCronicas=%s, Alergias=%s, AntecedentesFamiliares=%s WHERE ID=%s',
                (nombre_paciente, fecha_nacimiento, enfermedades_cronicas, alergias, antecedentes_familiares, id)
            )

            mysql.connection.commit()
            cursor.close()

            flash('Registro actualizado correctamente', 'success')
            return redirect(url_for('consultaP'))

        # Método GET: cargar el expediente para edición
        else:
            cursor = mysql.connection.cursor()
            cursor.execute('SELECT * FROM expedientes WHERE ID = %s', (id,))
            expediente = cursor.fetchone()
            cursor.close()

            if expediente:
                return render_template('editarExpe.html', expediente=expediente, expediente_id=id)
            else:
                flash('Expediente no encontrado', 'danger')
                return redirect(url_for('consultaP'))

    except Exception as e:
        flash('Error al actualizar el registro: ' + str(e), 'danger')
        return redirect(url_for('consultaP'))


#ruta para el formulario de expedientes
@app.route('/registrar_diagnostico', methods=['POST'])
@login_required
def registrar_diagnostico():
    cursor = mysql.connection.cursor()

    try:
        # Obtener los datos del formulario
        numeroDeExpediente = request.form['numeroDeExpediente'].upper()
        FechaConsulta = request.form['FechaConsulta']
        Peso = request.form['Peso']
        Altura = request.form['Altura']
        Temperatura = request.form['Temperatura']
        LatidosxMinuto = request.form['LatidosxMinuto']
        Glucosa = request.form['Glucosa']
        Sintomas = request.form['Sintomas']
        Diagnostico = request.form['Diagnostico']
        Tratamiento = request.form['Tratamiento']
        Indicaciones = request.form['Indicaciones']
        Estudios = request.form.get('Estudios', '')

        # Verificar si el expediente existe
        cursor.execute("SELECT * FROM expedientes WHERE NumeroExpediente = %s", [numeroDeExpediente])
        expediente = cursor.fetchone()
        if not expediente:
            flash("El número de expediente no existe.", "error")
            return render_template('consulta_exploracion_diagnostico.html', 
                                   numeroDeExpediente=numeroDeExpediente,
                                   FechaConsulta=FechaConsulta,
                                   Peso=Peso,
                                   Altura=Altura,
                                   Temperatura=Temperatura,
                                   LatidosxMinuto=LatidosxMinuto,
                                   Glucosa=Glucosa,
                                   Sintomas=Sintomas,
                                   Diagnostico=Diagnostico,
                                   Tratamiento=Tratamiento,
                                   Indicaciones=Indicaciones,
                                   Estudios=Estudios)

        # Calcular la edad del paciente
        fecha_nacimiento = expediente[3]  # Asumiendo que expediente[3] ya es un objeto datetime.date
        edad = datetime.now().year - fecha_nacimiento.year
        if datetime.now().month < fecha_nacimiento.month or (datetime.now().month == fecha_nacimiento.month and datetime.now().day < fecha_nacimiento.day):
            edad -= 1

        # Guardar en la tabla Diagnostico_y_Exploracion
        cursor.execute("""
            INSERT INTO Diagnostico_y_Exploracion (
                numeroDeExpediente, FechaConsulta, Peso, Altura, Temperatura, LatidosxMinuto, Glucosa,
                Sintomas, Diagnostico, Tratamiento, Indicaciones, Estudios
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (numeroDeExpediente, FechaConsulta, Peso, Altura, Temperatura, LatidosxMinuto, Glucosa,
              Sintomas, Diagnostico, Tratamiento, Indicaciones, Estudios))
        mysql.connection.commit()

        # Generar PDF con datos del expediente y diagnóstico
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        
        # Información del expediente
        pdf.set_font("Arial", "B", 16)
        pdf.cell(200, 10, txt="Receta Médica", ln=True, align='C')
        pdf.cell(200, 10, txt="Hospital San Cristo", ln=True, align='C')
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt=f"Médico: {session['nombre_medico']} (Cédula Profesional: {str(session['cedula'])})", ln=True)
        pdf.cell(200, 10, txt=f"Nombre del Paciente: {expediente[2]}", ln=True)
        pdf.cell(200, 10, txt=f"Fecha de Nacimiento: {fecha_nacimiento.strftime('%d/%m/%Y')}", ln=True)
        pdf.cell(200, 10, txt=f"Edad: {edad} años", ln=True)
        pdf.cell(200, 10, txt=f"Enfermedades Crónicas: {expediente[4]}", ln=True)
        pdf.cell(200, 10, txt=f"Alergias: {expediente[5]}", ln=True)
        pdf.cell(200, 10, txt=f"Antecedentes Familiares: {expediente[6]}", ln=True)
        
        # Información del diagnóstico
        pdf.ln(10)
        pdf.cell(200, 10, txt="Detalles de la Consulta", ln=True)
        pdf.cell(200, 10, txt=f"Fecha de Consulta: {FechaConsulta}", ln=True)
        pdf.cell(200, 10, txt=f"Peso: {Peso} kg", ln=True)
        pdf.cell(200, 10, txt=f"Altura: {Altura} cm", ln=True)
        pdf.cell(200, 10, txt=f"Temperatura: {Temperatura} °C", ln=True)
        pdf.cell(200, 10, txt=f"Latidos por Minuto: {LatidosxMinuto}", ln=True)
        pdf.cell(200, 10, txt=f"Glucosa: {Glucosa} mg/dL", ln=True)
        pdf.cell(200, 10, txt=f"Sintomas: {Sintomas}", ln=True)
        pdf.cell(200, 10, txt=f"Diagnóstico: {Diagnostico}", ln=True)
        pdf.cell(200, 10, txt=f"Tratamiento: {Tratamiento}", ln=True)
        pdf.cell(200, 10, txt=f"Indicaciones: {Indicaciones}", ln=True)
        if Estudios:
            pdf.cell(200, 10, txt=f"Estudios: {Estudios}", ln=True)

        # Añadir un espacio para la firma del médico
        pdf.ln(20)
        pdf.cell(200, 10, txt="Firma del Médico:", ln=True)
        pdf.cell(200, 10, txt="_", ln=True, align='C')
        
        # Generar un nombre de archivo único para la receta
        fecha_consulta_formateada = datetime.strptime(FechaConsulta, '%Y-%m-%d').strftime('%Y%m%d')
        pdf_filename = f"receta_{numeroDeExpediente}_{fecha_consulta_formateada}.pdf"
        pdf_output_path = os.path.join("static/recetas", pdf_filename)
        pdf.output(pdf_output_path)

        # Redirigir a la página 'tabla_citas'
        flash("Diagnóstico registrado y receta generada exitosamente.", "success")
        return redirect(url_for('citas_medico'))

    except MySQLdb.Error as e:
        mysql.connection.rollback()
        flash(f"Ocurrió un error al registrar el diagnóstico: {str(e)}", "error")
        return render_template('consulta_exploracion_diagnostico.html', 
                               numeroDeExpediente=numeroDeExpediente,
                               FechaConsulta=FechaConsulta,
                               Peso=Peso,
                               Altura=Altura,
                               Temperatura=Temperatura,
                               LatidosxMinuto=LatidosxMinuto,
                               Glucosa=Glucosa,
                               Sintomas=Sintomas,
                               Diagnostico=Diagnostico,
                               Tratamiento=Tratamiento,
                               Indicaciones=Indicaciones,
                               Estudios=Estudios)

    finally:
        cursor.close()

# ruta para buscar un usuario por su nombre
@app.route('/buscar_paciente', methods=['GET'])
@login_required
def buscar_paciente():
    medico_id = session['user_id']
    nombre = request.args.get('nombre', '').upper()  

    cursor = mysql.connection.cursor()
    query = """
        SELECT * FROM expedientes
        WHERE Medico = %s AND UPPER(NombrePaciente) LIKE %s
    """
    cursor.execute(query, (medico_id, f"%{nombre}%"))
    pacientes = cursor.fetchall()
    cursor.close()

    return render_template('ConsultaP.html', pacientes=pacientes)


# Manejo de excepciones para rutas no encontradas
@app.errorhandler(404)
def paginano(e):
    return 'Revisa tu sintaxis: PAGINA NO ENCONTRADA'


#ruta para el formulario de la cita medica del paciente
@app.route('/consulta_exploracion_diagnostigo')
@login_required
def consulta_exploracion_diagnostigo():
    return render_template('consulta_exploracion_diagnostico.html')



@app.route('/imprimir_receta/<int:cita_id>')
@login_required
def imprimir_receta(cita_id):
    cursor = mysql.connection.cursor()
    try:
        # Obtener el numeroDeExpediente asociado a la cita
        cursor.execute("""
            SELECT numeroDeExpediente
            FROM diagnostico_y_exploracion
            WHERE id = %s
        """, [cita_id])
        result = cursor.fetchone()

        if not result:
            raise FileNotFoundError("Número de expediente no encontrado para esta cita")

        numeroDeExpediente = result[0]

        # Asumir que los archivos PDF están guardados en la carpeta "static/recetas"
        pdf_directory = "static/recetas"
        partial_pdf_filename = f"receta_{numeroDeExpediente}"

        # Buscar archivos que coincidan con el patrón parcial
        matching_files = [f for f in os.listdir(pdf_directory) if f.startswith(partial_pdf_filename)]

        if not matching_files:
            raise FileNotFoundError("Receta no encontrada")

        # Si se encuentra el archivo, usar el primero de la lista (debería haber solo uno)
        pdf_filename = matching_files[0]
        pdf_output_path = os.path.join(pdf_directory, pdf_filename)

        # Enviar el archivo PDF
        return send_file(pdf_output_path, as_attachment=True)

    except FileNotFoundError as e:
        flash(str(e), "error")
        return redirect(url_for('citas_medico'))

    except Exception as e:
        flash(f"Ocurrió un error al intentar imprimir la receta: {str(e)}", "error")
        return redirect(url_for('citas_medico'))
    finally:
        cursor.close()


# ruta para visualizar las citas medicas y filtrarlas si es necesario
@app.route('/citas_medico', methods=['GET', 'POST'])
@login_required
def citas_medico():
    cursor = mysql.connection.cursor()
    medico_id = session['user_id']
    
    # Inicializar la consulta base
    query = """
        SELECT de.id, de.numeroDeExpediente, e.NombrePaciente, de.FechaConsulta
        FROM Diagnostico_y_Exploracion de
        JOIN expedientes e ON de.numeroDeExpediente = e.NumeroExpediente
        WHERE e.Medico = %s
    """
    params = [medico_id]
    
    # Añadir condiciones si existen criterios de búsqueda
    if request.method == 'POST':
        buscar_nombre = request.form.get('buscar_nombre', '').strip()
        buscar_expediente = request.form.get('buscar_expediente', '').strip()
        buscar_fecha = request.form.get('buscar_fecha', '').strip()

        if buscar_nombre:
            query += " AND e.NombrePaciente LIKE %s"
            params.append(f"%{buscar_nombre}%")
        
        if buscar_expediente:
            query += " AND de.numeroDeExpediente LIKE %s"
            params.append(f"%{buscar_expediente}%")
        
        if buscar_fecha:
            query += " AND de.FechaConsulta = %s"
            params.append(buscar_fecha)
    
    # Ejecutar la consulta
    cursor.execute(query, params)
    citas = cursor.fetchall()
    cursor.close()
    
    # Verificación de si la solicitud es AJAX
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return render_template('partials/citas_table.html', citas=citas)
    
    return render_template('tabla_citas.html', citas=citas)



if __name__ == '__main__':
    # puerto donde se ejecutará la aplicación y debug=True activa el modo de depuración.
    app.run(port=4000, debug=True)
