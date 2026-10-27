
from django.db import models
 
 
# ---------------------------------------------------------------------------
# Opciones compartidas
# ---------------------------------------------------------------------------
 
class TipoFondo(models.IntegerChoices):
    FONDO_0 = 0, "Fondo 0 (Protección de capital)"
    FONDO_1 = 1, "Fondo 1 (Preservación de capital)"
    FONDO_2 = 2, "Fondo 2 (Mixto)"
    FONDO_3 = 3, "Fondo 3 (Apreciación del capital)"
 
 
class TipoRentabilidad(models.TextChoices):
    NOMINAL = "nominal", "Nominal"
    REAL = "real", "Real"
 
 
# ---------------------------------------------------------------------------
# Catálogos
# ---------------------------------------------------------------------------
 
class Afp(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
 
    class Meta:
        db_table = "estadisticas_afp"
        verbose_name = "AFP"
        verbose_name_plural = "AFP"
 
    def __str__(self):
        return self.nombre
 
 
class Departamento(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
 
    class Meta:
        db_table = "estadisticas_departamento"
        verbose_name = "Departamento"
        verbose_name_plural = "Departamentos"
 
    def __str__(self):
        return self.nombre
 
 
class Pais(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
 
    class Meta:
        db_table = "estadisticas_pais"
        verbose_name = "País"
        verbose_name_plural = "Países"
 
    def __str__(self):
        return self.nombre
 
 
class Instrumento(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
 
    class Meta:
        db_table = "estadisticas_instrumento"
        verbose_name = "Instrumento"
        verbose_name_plural = "Instrumentos"
 
    def __str__(self):
        return self.nombre
 
 
class IndicadorAfp(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
 
    class Meta:
        db_table = "estadisticas_indicador_afp"
        verbose_name = "Indicador de AFP"
        verbose_name_plural = "Indicadores de AFP"
 
    def __str__(self):
        return self.nombre
 
 
class Concepto(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
 
    class Meta:
        db_table = "estadisticas_concepto"
        verbose_name = "Concepto"
        verbose_name_plural = "Conceptos"
 
    def __str__(self):
        return self.nombre
 
 
class TipoIngreso(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
 
    class Meta:
        db_table = "estadisticas_tipo_ingreso"
        verbose_name = "Tipo de ingreso"
        verbose_name_plural = "Tipos de ingreso"
 
    def __str__(self):
        return self.nombre
 
 
class TipoOperativo(models.Model):
    nombre = models.CharField(max_length=150, unique=True)
 
    class Meta:
        db_table = "estadisticas_tipo_operativo"
        verbose_name = "Tipo operativo"
        verbose_name_plural = "Tipos operativos"
 
    def __str__(self):
        return self.nombre
 
 
# ---------------------------------------------------------------------------
# Afiliados, cotizantes y traspasos
# ---------------------------------------------------------------------------
 
class Afiliados(models.Model):
    periodo = models.DateField()
    cantidad_afiliados = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_afiliados"
        verbose_name = "Estadística de afiliados"
        verbose_name_plural = "Estadísticas de afiliados"
        constraints = [
            models.UniqueConstraint(fields=["periodo"], name="afiliados_unico_periodo")
        ]
 
    def __str__(self):
        return f"Afiliados - {self.periodo}"
 
 
class AfiliadosActivosAfp(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="afiliados_activos")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_afiliados_activos_afp"
        verbose_name = "Afiliados activos por AFP"
        verbose_name_plural = "Afiliados activos por AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="afiliados_activos_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class AfiliadosActivosTipoFondo(models.Model):
    tipo_fondo = models.PositiveSmallIntegerField(choices=TipoFondo.choices)
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_afiliados_activos_tipo_fondo"
        verbose_name = "Afiliados activos por tipo de fondo"
        verbose_name_plural = "Afiliados activos por tipo de fondo"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_fondo", "anio"],
                name="afiliados_activos_unico_fondo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.get_tipo_fondo_display()} - {self.anio}"
 
 
class AfiliadosActivosDepartamento(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="afiliados_activos"
    )
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_afiliados_activos_departamento"
        verbose_name = "Afiliados activos por departamento"
        verbose_name_plural = "Afiliados activos por departamento"
        constraints = [
            models.UniqueConstraint(
                fields=["departamento", "anio"],
                name="afiliados_activos_unico_depto_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.departamento} - {self.anio}"
 
 
class AfiliadosActivosTipoComision(models.Model):
    afp = models.ForeignKey(
        Afp, on_delete=models.PROTECT, related_name="afiliados_activos_tipo_comision"
    )
    anio = models.PositiveSmallIntegerField()
    mixta = models.PositiveBigIntegerField()
    remuneracion = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_afiliados_activos_tipo_comision"
        verbose_name = "Afiliados activos por tipo de comisión"
        verbose_name_plural = "Afiliados activos por tipo de comisión"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="afiliados_activos_unico_comision_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class NuevosAfiliadosAfp(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="nuevos_afiliados")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_nuevos_afiliados_afp"
        verbose_name = "Nuevos afiliados por AFP"
        verbose_name_plural = "Nuevos afiliados por AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="nuevos_afiliados_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class TraspasosEfectivosAfpAnual(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="traspasos_anuales")
    anio = models.PositiveSmallIntegerField()
    ingreso = models.PositiveBigIntegerField()
    salida = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_traspasos_efectivos_afp_anual"
        verbose_name = "Traspasos efectivos por AFP (anual)"
        verbose_name_plural = "Traspasos efectivos por AFP (anual)"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="traspasos_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class MovimientoFondosTraspasos(models.Model):
    afp = models.ForeignKey(
        Afp, on_delete=models.PROTECT, related_name="movimientos_fondos_traspasos"
    )
    anio = models.PositiveSmallIntegerField()
    ingreso = models.DecimalField(max_digits=20, decimal_places=2)
    salida = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_movimiento_fondos_traspasos"
        verbose_name = "Movimiento de fondos por traspasos"
        verbose_name_plural = "Movimientos de fondos por traspasos"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="movimiento_fondos_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class CotizantesAfp(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="cotizantes")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cotizantes_afp"
        verbose_name = "Cotizantes por AFP"
        verbose_name_plural = "Cotizantes por AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="cotizantes_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class IndiceCotizantesAfp(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="indices_cotizantes")
    anio = models.PositiveSmallIntegerField()
    indice = models.DecimalField(max_digits=7, decimal_places=4)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_indice_cotizantes_afp"
        verbose_name = "Índice de cotizantes por AFP"
        verbose_name_plural = "Índices de cotizantes por AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "anio"],
                name="indice_cotizantes_unico_afp_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - {self.anio}"
 
 
class CotizantesDepartamento(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="cotizantes"
    )
    anio = models.PositiveSmallIntegerField()
    cotizantes = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cotizantes_departamento"
        verbose_name = "Cotizantes por departamento"
        verbose_name_plural = "Cotizantes por departamento"
        constraints = [
            models.UniqueConstraint(
                fields=["departamento", "anio"],
                name="cotizantes_unico_depto_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.departamento} - {self.anio}"
 
 
# ---------------------------------------------------------------------------
# Cartera administrada, valor cuota y rentabilidad (por AFP / fondo)
# ---------------------------------------------------------------------------
 
# TODO: confirmar si es por departamento o por AFP. Si es por AFP, cambiar el
# campo a `afp = ForeignKey(Afp, ...)` y renombrar el modelo.
class CarteraAdministradaAfp(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT, related_name="cartera_administrada"
    )
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cartera_administrada_afp"
        verbose_name = "Cartera administrada por AFP"
        verbose_name_plural = "Cartera administrada por AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["departamento", "anio"],
                name="cartera_administrada_unico_depto_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.departamento} - {self.anio}"
 
 
class CarteraAdministradaAfpTipoFondo(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="cartera_tipo_fondo")
    anio = models.PositiveSmallIntegerField()
    fondo = models.PositiveSmallIntegerField(choices=TipoFondo.choices)
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cartera_administrada_afp_tipo_fondo"
        verbose_name = "Cartera administrada por AFP y tipo de fondo"
        verbose_name_plural = "Cartera administrada por AFP y tipo de fondo"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "fondo", "anio"],
                name="cartera_tipo_fondo_unico_afp_fondo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - Fondo {self.fondo} - {self.anio}"
 
 
class CarteraAdministradaInstrumento(models.Model):
    instrumento = models.ForeignKey(
        Instrumento, on_delete=models.PROTECT, related_name="cartera_administrada"
    )
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cartera_administrada_instrumento"
        verbose_name = "Cartera administrada por instrumento"
        verbose_name_plural = "Cartera administrada por instrumento"
        constraints = [
            models.UniqueConstraint(
                fields=["instrumento", "anio"],
                name="cartera_instrumento_unico_instr_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.instrumento} - {self.anio}"
 
 
class ValorCuotaTipoFondoAfp(models.Model):
    afp = models.ForeignKey(Afp, on_delete=models.PROTECT, related_name="valores_cuota")
    anio = models.PositiveSmallIntegerField()
    fondo = models.PositiveSmallIntegerField(choices=TipoFondo.choices)
    monto = models.DecimalField(max_digits=14, decimal_places=6)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_valor_cuota_tipo_fondo_afp"
        verbose_name = "Valor cuota por tipo de fondo y AFP"
        verbose_name_plural = "Valores cuota por tipo de fondo y AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["afp", "fondo", "anio"],
                name="valor_cuota_unico_afp_fondo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.afp} - Fondo {self.fondo} - {self.anio}"
 
 
class RentabilidadTipoFondo(models.Model):
    tipo_rentabilidad = models.CharField(max_length=20, choices=TipoRentabilidad.choices)
    anio = models.PositiveSmallIntegerField()
    fondo = models.PositiveSmallIntegerField(choices=TipoFondo.choices)
    monto = models.DecimalField(max_digits=8, decimal_places=4)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_rentabilidad_tipo_fondo"
        verbose_name = "Rentabilidad por tipo de fondo"
        verbose_name_plural = "Rentabilidades por tipo de fondo"
        constraints = [
            models.UniqueConstraint(
                fields=["tipo_rentabilidad", "fondo", "anio"],
                name="rentabilidad_unica_tipo_fondo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.get_tipo_rentabilidad_display()} - Fondo {self.fondo} - {self.anio}"
 
 
# ---------------------------------------------------------------------------
# Indicadores y comisiones
# ---------------------------------------------------------------------------
 
# TODO: confirmar si `ratio` es un número o el nombre de un ratio (texto).
# Si es texto, cambiarlo a CharField e incluirlo en el UniqueConstraint.
class IndicadoresAfp(models.Model):
    indicador = models.ForeignKey(
        IndicadorAfp, on_delete=models.PROTECT, related_name="valores"
    )
    anio = models.PositiveSmallIntegerField()
    ratio = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    monto = models.DecimalField(max_digits=20, decimal_places=2, null=True, blank=True)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_indicadores_afp"
        verbose_name = "Indicadores de AFP"
        verbose_name_plural = "Indicadores de AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["indicador", "anio"],
                name="indicadores_unico_indicador_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.indicador} - {self.anio}"
 
 
class ComisionesPrimaSegurosAfp(models.Model):
    concepto = models.ForeignKey(
        Concepto, on_delete=models.PROTECT, related_name="comisiones_prima_seguros"
    )
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=20, decimal_places=4)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_comisiones_prima_seguros_afp"
        verbose_name = "Comisiones y prima de seguros de AFP"
        verbose_name_plural = "Comisiones y prima de seguros de AFP"
        constraints = [
            models.UniqueConstraint(
                fields=["concepto", "anio"],
                name="comisiones_prima_unico_concepto_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.concepto} - {self.anio}"
 
 
# ---------------------------------------------------------------------------
# Comparación internacional (por país)
# ---------------------------------------------------------------------------
 
class EvolucionAfiliados(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="evolucion_afiliados")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_evolucion_afiliados"
        verbose_name = "Evolución de afiliados"
        verbose_name_plural = "Evolución de afiliados"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="evolucion_afiliados_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class EvolucionAfiliadosPea(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="evolucion_afiliados_pea")
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=7, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_evolucion_afiliados_pea"
        verbose_name = "Evolución de afiliados como % de la PEA"
        verbose_name_plural = "Evolución de afiliados como % de la PEA"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="evolucion_afiliados_pea_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class EvolucionAportantes(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="evolucion_aportantes")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_evolucion_aportantes"
        verbose_name = "Evolución de aportantes"
        verbose_name_plural = "Evolución de aportantes"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="evolucion_aportantes_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class EvolucionAportantesPea(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="evolucion_aportantes_pea")
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=7, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_evolucion_aportantes_pea"
        verbose_name = "Evolución de aportantes como % de la PEA"
        verbose_name_plural = "Evolución de aportantes como % de la PEA"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="evolucion_aportantes_pea_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class EvolucionBeneficiarios(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="evolucion_beneficiarios")
    anio = models.PositiveSmallIntegerField()
    monto = models.PositiveBigIntegerField()
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_evolucion_beneficiarios"
        verbose_name = "Evolución de beneficiarios"
        verbose_name_plural = "Evolución de beneficiarios"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="evolucion_beneficiarios_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class CarteraAdministrada(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="cartera_administrada")
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cartera_administrada"
        verbose_name = "Cartera administrada"
        verbose_name_plural = "Cartera administrada"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="cartera_administrada_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class CarteraAdministradaPct(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="cartera_administrada_pct")
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=7, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_cartera_administrada_pct"
        verbose_name = "Cartera administrada (% del PBI)"
        verbose_name_plural = "Cartera administrada (% del PBI)"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="cartera_administrada_pct_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"
 
 
class RentabilidadAnualizadaFondosPensiones(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="rentabilidad_anualizada")
    tipo_rentabilidad = models.CharField(max_length=20, choices=TipoRentabilidad.choices)
    anio = models.PositiveSmallIntegerField()
    horizonte = models.CharField(max_length=30)
    monto = models.DecimalField(max_digits=8, decimal_places=4)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_rentabilidad_anualizada_fondos_pensiones"
        verbose_name = "Rentabilidad anualizada de fondos de pensiones"
        verbose_name_plural = "Rentabilidades anualizadas de fondos de pensiones"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "tipo_rentabilidad", "horizonte", "anio"],
                name="rent_anualizada_unica_pais_tipo_horizonte_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.get_tipo_rentabilidad_display()} - {self.horizonte} - {self.anio}"
 
 
class BalanceAdministradoras(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="balance_administradoras")
    anio = models.PositiveSmallIntegerField()
    tipo_ingreso = models.ForeignKey(
        TipoIngreso, on_delete=models.PROTECT, related_name="balance_administradoras"
    )
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_balance_administradoras"
        verbose_name = "Balance de administradoras"
        verbose_name_plural = "Balance de administradoras"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "tipo_ingreso", "anio"],
                name="balance_adm_unico_pais_tipo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.tipo_ingreso} - {self.anio}"
 
 
class ResultadosAnualesAdministradoras(models.Model):
    pais = models.ForeignKey(
        Pais, on_delete=models.PROTECT, related_name="resultados_anuales_administradoras"
    )
    anio = models.PositiveSmallIntegerField()
    tipo_ingreso = models.ForeignKey(
        TipoIngreso, on_delete=models.PROTECT, related_name="resultados_anuales_administradoras"
    )
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_resultados_anuales_administradoras"
        verbose_name = "Resultados anuales de administradoras"
        verbose_name_plural = "Resultados anuales de administradoras"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "tipo_ingreso", "anio"],
                name="resultados_adm_unico_pais_tipo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.tipo_ingreso} - {self.anio}"
 
 
class ResultadosAnualesAdministradorasOperativo(models.Model):
    pais = models.ForeignKey(
        Pais, on_delete=models.PROTECT, related_name="resultados_anuales_operativo"
    )
    anio = models.PositiveSmallIntegerField()
    tipo_operativo = models.ForeignKey(
        TipoOperativo, on_delete=models.PROTECT, related_name="resultados_anuales_operativo"
    )
    monto = models.DecimalField(max_digits=20, decimal_places=2)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_resultados_anuales_administradoras_operativo"
        verbose_name = "Resultados anuales de administradoras (operativo)"
        verbose_name_plural = "Resultados anuales de administradoras (operativo)"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "tipo_operativo", "anio"],
                name="resultados_operativo_unico_pais_tipo_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.tipo_operativo} - {self.anio}"
 
 
class RatioGastosOperativo(models.Model):
    pais = models.ForeignKey(Pais, on_delete=models.PROTECT, related_name="ratio_gastos_operativo")
    anio = models.PositiveSmallIntegerField()
    monto = models.DecimalField(max_digits=9, decimal_places=4)
    fecha_carga = models.DateTimeField(auto_now_add=True)
 
    class Meta:
        db_table = "estadisticas_ratio_gastos_operativo"
        verbose_name = "Ratio de gastos operativos"
        verbose_name_plural = "Ratios de gastos operativos"
        constraints = [
            models.UniqueConstraint(
                fields=["pais", "anio"],
                name="ratio_gastos_operativo_unico_pais_anio",
            )
        ]
 
    def __str__(self):
        return f"{self.pais} - {self.anio}"