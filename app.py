"""
app.py
------
Interfaz web (ControladorUI) del Simulador de Saturación Hospitalaria.

Conecta las tres piezas del proyecto:
    - model.py     -> la ecuación de acumulación (MotorSimulacion)
    - database.py  -> persistencia de escenarios en SQLite
    - templates/   -> las 4 pantallas (Configurar, Resultados, Comparar, Exportar)

Para ejecutar:
    pip install -r requirements.txt
    python app.py
Luego abrir http://127.0.0.1:5000 en el navegador.
"""

import csv
import io

from flask import Flask, render_template, request, redirect, url_for, flash, Response

import database as db
from model import ParametrosSimulacion, MotorSimulacion

app = Flask(__name__)
app.secret_key = "clave-de-desarrollo-taller-modelamiento"  # basta para uso local/académico


@app.context_processor
def inject_ultimo_id():
    """Hace disponible 'ultimo_id' en todas las plantillas, para los enlaces del nav."""
    escenarios = db.listar_escenarios()
    return {"ultimo_id": escenarios[0]["id"] if escenarios else None}


@app.route("/")
def configurar():
    siguiente_num = len(db.listar_escenarios()) + 1
    return render_template("configurar.html", active="configurar", siguiente_num=siguiente_num)


@app.route("/simular", methods=["POST"])
def simular():
    try:
        semilla_raw = request.form.get("semilla", "").strip()
        politica_activa = request.form.get("politica_activa") == "on"
        umbral_raw = request.form.get("umbral_politica", "90").strip()
        params = ParametrosSimulacion(
            ocupacion_inicial=float(request.form["ocupacion_inicial"]),
            tasa_admisiones=float(request.form["tasa_admisiones"]),
            estancia_promedio=float(request.form["estancia_promedio"]),
            capacidad_actual=float(request.form["capacidad_actual"]),
            capacidad_futura=float(request.form["capacidad_futura"]),
            dias=int(request.form["dias"]),
            variabilidad=float(request.form["variabilidad"]),
            semilla=int(semilla_raw) if semilla_raw else None,
            politica_activa=politica_activa,
            umbral_politica=(float(umbral_raw) / 100) if umbral_raw else 0.9,
        )
        resultado = MotorSimulacion(params).ejecutar()
        nombre = request.form.get("nombre", "").strip() or "Escenario sin nombre"
        escenario_id = db.guardar_escenario(nombre, params, resultado)
    except ValueError as e:
        flash(f"No se pudo ejecutar la simulación: {e}")
        return redirect(url_for("configurar"))

    return redirect(url_for("resultados", escenario_id=escenario_id))


@app.route("/resultados/<int:escenario_id>")
def resultados(escenario_id):
    datos = db.obtener_resultado_completo(escenario_id)
    if datos is None:
        flash("Ese escenario no existe.")
        return redirect(url_for("configurar"))

    escenario = datos["escenario"]
    resultado = datos["resultado"]
    ocupacion_por_dia = datos["ocupacion_por_dia"]

    # Reconstruye los parámetros exactos usados (misma semilla) para poder
    # recalcular la capacidad mínima necesaria y, si aplica, la línea base
    # "sin política" con la MISMA demanda, solo para efectos de comparación
    # en pantalla (no se vuelve a guardar en la base de datos).
    params = ParametrosSimulacion(
        ocupacion_inicial=escenario["ocupacion_inicial"],
        tasa_admisiones=escenario["tasa_admisiones"],
        estancia_promedio=escenario["estancia_promedio"],
        capacidad_actual=escenario["capacidad_actual"],
        capacidad_futura=escenario["capacidad_futura"],
        dias=escenario["dias"],
        variabilidad=escenario["variabilidad"],
        semilla=escenario["semilla"],
        politica_activa=bool(escenario["politica_activa"]),
        umbral_politica=escenario["umbral_politica"],
    )
    motor = MotorSimulacion(params)
    capacidad_minima = motor.capacidad_minima_necesaria

    ocupacion_sin_politica = None
    recomendacion = None
    if escenario["politica_activa"]:
        ocupacion_sin_politica = motor.ejecutar(aplicar_politica=False).ocupacion_por_dia
        if resultado["dia_saturacion"] is None:
            recomendacion = (
                f"Con la política de derivación activa al {int(escenario['umbral_politica']*100)}% "
                f"de la capacidad actual, el hospital NO llega a saturarse: la ocupación se estabiliza "
                f"en {resultado['ocupacion_final']} camas, frente a las {ocupacion_sin_politica[-1]} camas "
                f"que habría alcanzado sin la política."
            )
        else:
            recomendacion = (
                f"Incluso con la política activa, la ocupación supera la capacidad el día "
                f"{resultado['dia_saturacion']}. La política reduce el impacto (ocupación final de "
                f"{resultado['ocupacion_final']} camas frente a {ocupacion_sin_politica[-1]} sin política), "
                f"pero no es suficiente por sí sola: convendría además aumentar la capacidad o reducir la demanda."
            )
    elif resultado["dia_saturacion"] is not None:
        recomendacion = (
            f"Este escenario se satura el día {resultado['dia_saturacion']}. Una posible solución: activar "
            f"una política de derivación al 90% de la capacidad desde la pantalla Configurar, o aumentar la "
            f"capacidad hasta al menos {capacidad_minima} camas (el nivel de equilibrio de este escenario)."
        )

    return render_template(
        "resultados.html", active="resultados",
        escenario=escenario, resultado=resultado,
        ocupacion_por_dia=ocupacion_por_dia,
        ocupacion_sin_politica=ocupacion_sin_politica,
        dias_labels=list(range(len(ocupacion_por_dia))),
        capacidad_minima=capacidad_minima,
        recomendacion=recomendacion,
    )


@app.route("/comparar", methods=["GET", "POST"])
def comparar():
    escenarios = db.listar_escenarios()

    seleccionados = []
    datasets, labels, resumen = None, None, None

    if request.method == "POST":
        seleccionados = [int(i) for i in request.form.getlist("ids")]
        if seleccionados:
            datasets, resumen = [], []
            max_len = 0
            for eid in seleccionados:
                datos = db.obtener_resultado_completo(eid)
                if datos is None:
                    continue
                serie = datos["ocupacion_por_dia"]
                max_len = max(max_len, len(serie))
                datasets.append({"nombre": datos["escenario"]["nombre"], "ocupacion": serie})
                resumen.append({
                    "nombre": datos["escenario"]["nombre"],
                    "dia_saturacion": datos["resultado"]["dia_saturacion"],
                    "ocupacion_final": datos["resultado"]["ocupacion_final"],
                })
            labels = list(range(max_len))

    return render_template(
        "comparar.html", active="comparar", escenarios=escenarios,
        seleccionados=seleccionados, datasets=datasets, labels=labels, resumen=resumen,
    )


@app.route("/exportar/<int:escenario_id>")
def exportar(escenario_id):
    datos = db.obtener_resultado_completo(escenario_id)
    if datos is None:
        flash("Ese escenario no existe.")
        return redirect(url_for("configurar"))

    return render_template(
        "exportar.html", active="exportar",
        escenario=datos["escenario"], resultado=datos["resultado"],
        ocupacion_por_dia=datos["ocupacion_por_dia"],
    )


@app.route("/exportar/<int:escenario_id>/csv")
def exportar_csv(escenario_id):
    datos = db.obtener_resultado_completo(escenario_id)
    if datos is None:
        flash("Ese escenario no existe.")
        return redirect(url_for("configurar"))

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["dia", "ocupacion_H(t)"])
    for dia, valor in enumerate(datos["ocupacion_por_dia"]):
        writer.writerow([dia, valor])

    nombre_archivo = f"resultados_{datos['escenario']['nombre'].replace(' ', '_')}.csv"
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={nombre_archivo}"},
    )


if __name__ == "__main__":
    db.init_db()
    app.run(debug=True)
