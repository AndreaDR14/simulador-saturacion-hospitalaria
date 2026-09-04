# Simulador de Saturación Hospitalaria

Software desarrollado para el taller "De la Realidad a la Ecuación" —
Modelamiento de Sistemas, Unidad 1, Universidad de Cundinamarca.

Implementa la ecuación de acumulación del Hospital San Rafael de Fusagasugá:

    H(t+1) = H(t) + A - H(t) / T

con base de datos SQLite para guardar escenarios, e interfaz web para
configurarlos, ejecutarlos, compararlos y exportarlos — siguiendo los mismos
4 pasos y las mismas pantallas definidas en los diagramas UML y los bocetos
del proyecto.

Además de diagnosticar el problema (¿cuándo se satura el hospital?), el
software también ofrece una **solución**: una política de derivación que,
al llegar a un porcentaje configurable de la capacidad actual, deja de
admitir pacientes por encima de lo que se da de alta ese día. La pantalla
de Resultados compara automáticamente "con política" contra "sin política"
en la misma gráfica, y muestra una recomendación en texto.

## Requisitos

- Python 3.9 o superior
- El archivo `chart.umd.min.js` (Chart.js) dentro de `static/`, ya que esta
  versión del proyecto está configurada para usarlo de forma local (no desde
  un CDN), para evitar bloqueos de "Tracking Prevention" en algunos
  navegadores. Si no lo tienen aún:
  1. Abran en el navegador: https://cdn.jsdelivr.net/npm/chart.js@4.4.4/dist/chart.umd.min.js
  2. Ctrl+S para guardarlo, con el nombre exacto `chart.umd.min.js`
  3. Muévanlo dentro de la carpeta `static/` del proyecto, junto a `style.css`

## Instalación y ejecución

```bash
pip install -r requirements.txt
python app.py
```

Luego abran en el navegador: **http://127.0.0.1:5000**

La primera vez que se ejecuta, se crea automáticamente el archivo
`instance/simulador.db` (SQLite) con las tablas necesarias — no requiere
ninguna instalación adicional de base de datos ni servidor corriendo.

## Estructura del proyecto

```
simulador_hospital/
├── app.py              # Controlador web (Flask) — equivale a ControladorUI en el UML
├── model.py             # Motor matemático — ParametrosSimulacion, ResultadoSimulacion, MotorSimulacion
├── database.py           # Acceso a datos SQLite — guardar y consultar escenarios
├── requirements.txt
├── instance/
│   └── simulador.db      # Base de datos (se crea sola al ejecutar)
├── static/
│   └── style.css
└── templates/
    ├── base.html          # Navegación común a las 4 pantallas
    ├── configurar.html    # Pantalla 1 — Configurar Parámetros del Modelo
    ├── resultados.html    # Pantalla 2 — Resultados de la Simulación
    ├── comparar.html       # Pantalla 3 — Comparar Escenarios
    └── exportar.html       # Pantalla 4 — Exportar Reporte
```

## Relación con los entregables anteriores del taller

| Entregable                     | Dónde se ve reflejado en el código                                   |
|---------------------------------|------------------------------------------------------------------------|
| Informe APA 7 (Pasos 1-4)      | `model.py` implementa exactamente la ecuación y los supuestos (H(0)=120, A=22, T=8) |
| Pregunta de discusión sobre el "punto de reorden" | Implementada como la política de derivación (`politica_activa`, `umbral_politica` en `model.py`) — ya no es solo una respuesta en texto, se puede simular |
| Diagrama de Casos de Uso        | Las 4 rutas principales de `app.py` (`/`, `/resultados`, `/comparar`, `/exportar`) |
| Diagrama de Clases              | `ParametrosSimulacion`, `ResultadoSimulacion`, `MotorSimulacion` en `model.py` son las mismas clases del diagrama |
| Diagrama de Secuencia           | La función `simular()` en `app.py` sigue el mismo flujo: recibe parámetros → `MotorSimulacion.ejecutar()` → guarda en BD → redirige a resultados |
| Bocetos de Figma                | Las 4 plantillas HTML siguen el mismo layout que los bocetos en gris |

## Probar rápido sin la interfaz web

```bash
python model.py
```

Corre una simulación de ejemplo por consola con los mismos parámetros del
informe (H(0)=120, A=22, T=8, 30 días) y una semilla fija (42) para que el
resultado sea reproducible.

## Si el navegador muestra la gráfica en blanco

Revisen que exista el archivo `static/chart.umd.min.js` (ver sección de
Requisitos arriba) — sin él, la gráfica no tiene con qué dibujarse. Si ya
existe y aun así no aparece, abran la consola del navegador (F12 → Console)
y revisen el mensaje de error exacto.
