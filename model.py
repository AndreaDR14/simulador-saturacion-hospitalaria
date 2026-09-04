"""
model.py
--------
Modelo dinámico de saturación de camas — Hospital San Rafael de Fusagasugá.

Implementa la ecuación de acumulación desarrollada en el informe
"De la Realidad a la Ecuación":

    H(t+1) = H(t) + A - H(t) / T

Donde:
    H(t) : camas ocupadas en el día t              (variable de estado)
    A    : tasa de admisiones (pacientes/día)       (entrada)
    T    : estancia promedio (días)                 (usada para la salida)

Además de diagnosticar el problema (¿cuándo se satura?), este módulo
también ofrece una posible SOLUCIÓN: una política de derivación que,
al alcanzar un porcentaje de la capacidad actual, deja de admitir
pacientes por encima de lo que se da de alta ese día -es decir, deriva
el exceso de demanda a otra institución-, evitando que la ocupación
siga creciendo sin control. Esta es la misma idea planteada en la
sección de Discusión del informe, ahora implementada y simulada.
"""

from dataclasses import dataclass, field
from typing import List, Optional
import random


@dataclass
class ParametrosSimulacion:
    """Agrupa todos los supuestos y condiciones iniciales del modelo."""

    ocupacion_inicial: float       # H(0), camas ocupadas al día 0
    tasa_admisiones: float         # A, pacientes/día (entrada)
    estancia_promedio: float       # T, días (usada para calcular la salida)
    capacidad_actual: float        # camas disponibles hoy
    capacidad_futura: float        # camas disponibles desde la ampliación
    dias: int                      # horizonte de la simulación
    variabilidad: float = 5.0      # +/- pacientes/día de aleatoriedad en A
    semilla: Optional[int] = None  # fija la semilla para resultados reproducibles
    politica_activa: bool = False  # ¿aplicar la política de derivación?
    umbral_politica: float = 0.9   # fracción de la capacidad actual que activa la política

    def validar(self) -> None:
        """Lanza ValueError si algún parámetro no tiene sentido físico."""
        if self.ocupacion_inicial < 0:
            raise ValueError("La ocupación inicial no puede ser negativa.")
        if self.tasa_admisiones < 0:
            raise ValueError("La tasa de admisiones no puede ser negativa.")
        if self.estancia_promedio <= 0:
            raise ValueError("La estancia promedio debe ser mayor que cero.")
        if self.capacidad_actual <= 0 or self.capacidad_futura <= 0:
            raise ValueError("Las capacidades deben ser mayores que cero.")
        if self.dias <= 0:
            raise ValueError("El número de días a simular debe ser mayor que cero.")
        if self.variabilidad < 0:
            raise ValueError("La variabilidad no puede ser negativa.")
        if not (0 < self.umbral_politica <= 1):
            raise ValueError("El umbral de la política debe estar entre 0 y 1 (ej. 0.9 = 90%).")


@dataclass
class ResultadoSimulacion:
    """Salida de una corrida del modelo."""

    ocupacion_por_dia: List[float]     # H(0)..H(dias)
    dia_saturacion: Optional[int]      # primer día en que H(t) > capacidad_actual
    ocupacion_final: float             # H(dias)


class MotorSimulacion:
    """Ejecuta la ecuación de acumulación día a día (Paso 3 y Paso 4 del informe)."""

    def __init__(self, parametros: ParametrosSimulacion):
        parametros.validar()
        # Si no se especificó semilla, se genera una y se guarda en los propios
        # parámetros -- así, aunque la corrida sea "aleatoria", queda registrada
        # y se puede reproducir exactamente más adelante (por ejemplo, para
        # comparar "con política" contra "sin política" con la misma demanda).
        if parametros.semilla is None:
            parametros.semilla = random.randint(0, 999_999)
        self.parametros = parametros
        self._rng = random.Random(parametros.semilla)

        # La demanda de admisiones se precalcula UNA sola vez para los 'dias'
        # del horizonte. Así, cuando se ejecuta la misma simulación con y sin
        # política de derivación, ambas corridas parten de la misma demanda
        # real y la comparación es justa (solo cambia la política, no el azar).
        p = self.parametros
        self._admisiones_base = [
            p.tasa_admisiones + self._rng.randint(-int(p.variabilidad), int(p.variabilidad))
            for _ in range(p.dias)
        ]

    def _calcular_altas(self, nivel_actual: float) -> float:
        """E(t) = H(t) / T."""
        return nivel_actual / self.parametros.estancia_promedio

    @property
    def capacidad_minima_necesaria(self) -> float:
        """Nivel de equilibrio al que tiende H(t) a largo plazo: A * T.

        Es la capacidad mínima que debería tener el hospital para que, en
        promedio, la ocupación no crezca indefinidamente.
        """
        return round(self.parametros.tasa_admisiones * self.parametros.estancia_promedio, 1)

    def ejecutar(self, aplicar_politica: Optional[bool] = None) -> ResultadoSimulacion:
        """Corre la simulación día a día.

        aplicar_politica:
            None  -> usa parametros.politica_activa (comportamiento normal)
            True  -> fuerza la política de derivación, sin importar el parámetro
            False -> fuerza NO aplicar la política (para generar la línea base
                      de comparación "sin política", reutilizando la misma demanda)
        """
        p = self.parametros
        usar_politica = p.politica_activa if aplicar_politica is None else aplicar_politica
        umbral = p.umbral_politica * p.capacidad_actual

        ocupacion: List[float] = [round(p.ocupacion_inicial, 1)]
        dia_saturacion: Optional[int] = None

        for t in range(p.dias):
            altas_t = self._calcular_altas(ocupacion[-1])
            admisiones_t = self._admisiones_base[t]

            if usar_politica and ocupacion[-1] >= umbral:
                # Política de derivación: solo se admite lo necesario para
                # reponer las altas del día -el exceso de demanda se deriva
                # a otra institución-, evitando que el nivel siga subiendo.
                admisiones_t = min(admisiones_t, altas_t)

            nuevo_nivel = ocupacion[-1] + admisiones_t - altas_t
            nuevo_nivel = round(max(nuevo_nivel, 0), 1)
            ocupacion.append(nuevo_nivel)

            if dia_saturacion is None and nuevo_nivel > p.capacidad_actual:
                dia_saturacion = t + 1

        return ResultadoSimulacion(
            ocupacion_por_dia=ocupacion,
            dia_saturacion=dia_saturacion,
            ocupacion_final=ocupacion[-1],
        )


if __name__ == "__main__":
    # Prueba rápida por consola: python model.py
    params = ParametrosSimulacion(
        ocupacion_inicial=120, tasa_admisiones=22, estancia_promedio=8,
        capacidad_actual=141, capacidad_futura=205, dias=30, semilla=42,
        politica_activa=True, umbral_politica=0.9,
    )
    motor = MotorSimulacion(params)
    sin_politica = motor.ejecutar(aplicar_politica=False)
    con_politica = motor.ejecutar(aplicar_politica=True)

    print("Capacidad mínima necesaria (A x T):", motor.capacidad_minima_necesaria)
    print("SIN política -> día saturación:", sin_politica.dia_saturacion, "| final:", sin_politica.ocupacion_final)
    print("CON política -> día saturación:", con_politica.dia_saturacion, "| final:", con_politica.ocupacion_final)
