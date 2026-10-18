"""Modelos SQLAlchemy del sistema de logística de árbitros."""

from datetime import datetime

from .database import db


ESTADOS_VIAJE = ("Asignado", "Confirmado", "En camino", "En ciudad", "En estadio", "Finalizado")
ESTADOS_PAGO = ("Pendiente", "Pagado")
ESTADOS_PARTIDO = ("Programado", "En curso", "Finalizado")
ARBITROS_POR_PARTIDO = 2


def _numero(valor):
    return float(valor) if valor is not None else 0.0


class Estado(db.Model):
    __tablename__ = "estados"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    ciudades = db.relationship("Ciudad", back_populates="estado", lazy=True)
    aeropuertos = db.relationship("Aeropuerto", back_populates="estado", lazy=True)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre}


class Ciudad(db.Model):
    __tablename__ = "ciudades"
    __table_args__ = (db.UniqueConstraint("nombre", "estado_id", name="uq_ciudad_estado"),)
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    estado_id = db.Column(db.Integer, db.ForeignKey("estados.id", ondelete="RESTRICT"), nullable=False)
    estado = db.relationship("Estado", back_populates="ciudades")
    arbitros = db.relationship("Arbitro", back_populates="ciudad_origen", lazy=True)
    partidos = db.relationship("Partido", back_populates="ciudad_juego", lazy=True)
    distancias_origen = db.relationship("DistanciaCiudad", foreign_keys="DistanciaCiudad.ciudad_origen_id", back_populates="ciudad_origen", lazy=True)
    distancias_destino = db.relationship("DistanciaCiudad", foreign_keys="DistanciaCiudad.ciudad_destino_id", back_populates="ciudad_destino", lazy=True)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "estado_id": self.estado_id,
                "estado": self.estado.to_dict() if self.estado else None}


class EstadoCercano(db.Model):
    __tablename__ = "estados_cercanos"
    __table_args__ = (db.UniqueConstraint("estado_a_id", "estado_b_id", name="uq_estados_cercanos"),)
    id = db.Column(db.Integer, primary_key=True)
    estado_a_id = db.Column(db.Integer, db.ForeignKey("estados.id", ondelete="RESTRICT"), nullable=False)
    estado_b_id = db.Column(db.Integer, db.ForeignKey("estados.id", ondelete="RESTRICT"), nullable=False)


class Aeropuerto(db.Model):
    """Aeropuertos de referencia para estimar rutas aéreas entre estados venezolanos."""
    __tablename__ = "aeropuertos"
    __table_args__ = (db.UniqueConstraint("codigo_iata", name="uq_aeropuerto_iata"),)
    id = db.Column(db.Integer, primary_key=True)
    estado_id = db.Column(db.Integer, db.ForeignKey("estados.id", ondelete="RESTRICT"), nullable=False)
    ciudad_sede = db.Column(db.String(150), nullable=False)
    nombre = db.Column(db.String(220), nullable=False)
    codigo_iata = db.Column(db.String(3), nullable=False)
    latitud = db.Column(db.Numeric(10, 7), nullable=False)
    longitud = db.Column(db.Numeric(10, 7), nullable=False)
    principal = db.Column(db.Boolean, nullable=False, default=True)
    estado = db.relationship("Estado", back_populates="aeropuertos")

    def to_dict(self):
        return {"id": self.id, "estado_id": self.estado_id, "ciudad_sede": self.ciudad_sede,
                "nombre": self.nombre, "codigo_iata": self.codigo_iata, "latitud": _numero(self.latitud),
                "longitud": _numero(self.longitud), "principal": self.principal,
                "estado": self.estado.to_dict() if self.estado else None}


class DistanciaCiudad(db.Model):
    """Matriz de distancias por carretera entre ciudades de la liga."""
    __tablename__ = "distancias_ciudades"
    __table_args__ = (db.UniqueConstraint("ciudad_origen_id", "ciudad_destino_id", name="uq_distancia_ciudades"),)
    id = db.Column(db.Integer, primary_key=True)
    ciudad_origen_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False)
    ciudad_destino_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False)
    distancia_km = db.Column(db.Numeric(10, 2), nullable=False)
    ciudad_origen = db.relationship("Ciudad", foreign_keys=[ciudad_origen_id], back_populates="distancias_origen")
    ciudad_destino = db.relationship("Ciudad", foreign_keys=[ciudad_destino_id], back_populates="distancias_destino")

    def to_dict(self):
        return {"id": self.id, "ciudad_origen_id": self.ciudad_origen_id, "ciudad_destino_id": self.ciudad_destino_id,
                "distancia_km": _numero(self.distancia_km)}


class UbicacionCancha(db.Model):
    """Datos operativos de una sede; permiten enriquecer partidos sin alterar su estructura."""
    __tablename__ = "ubicaciones_cancha"
    __table_args__ = (db.UniqueConstraint("nombre_cancha", "ciudad_id", name="uq_cancha_ciudad"),)
    id = db.Column(db.Integer, primary_key=True)
    nombre_cancha = db.Column(db.String(150), nullable=False)
    ciudad_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False)
    direccion = db.Column(db.String(250))
    latitud = db.Column(db.Numeric(10, 7))
    longitud = db.Column(db.Numeric(10, 7))
    ciudad = db.relationship("Ciudad")

    def to_dict(self):
        return {"id": self.id, "nombre_cancha": self.nombre_cancha, "ciudad_id": self.ciudad_id,
                "direccion": self.direccion, "latitud": _numero(self.latitud) if self.latitud is not None else None,
                "longitud": _numero(self.longitud) if self.longitud is not None else None}


class TarifaTraslado(db.Model):
    __tablename__ = "tarifas_traslado"
    __table_args__ = (db.UniqueConstraint("tipo", "medio", name="uq_tarifa_tipo_medio"),)
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False)  # externo o interno
    medio = db.Column(db.String(20), nullable=False)  # avion o taxi
    costo_base = db.Column(db.Numeric(10, 2), nullable=False)


class TarifaHospedaje(db.Model):
    __tablename__ = "tarifas_hospedaje"
    id = db.Column(db.Integer, primary_key=True)
    ciudad_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False, unique=True)
    costo_noche = db.Column(db.Numeric(10, 2), nullable=False)
    ciudad = db.relationship("Ciudad")


class Parametro(db.Model):
    __tablename__ = "parametros"
    clave = db.Column(db.String(80), primary_key=True)
    valor = db.Column(db.Numeric(10, 2), nullable=False)


class Arbitro(db.Model):
    __tablename__ = "arbitros"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(80), nullable=False)
    apellido = db.Column(db.String(80), nullable=False)
    telefono = db.Column(db.String(30))
    email = db.Column(db.String(150))
    activo = db.Column(db.Boolean, nullable=False, default=True)
    ciudad_origen_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False)
    ciudad_origen = db.relationship("Ciudad", back_populates="arbitros")
    asignaciones = db.relationship("AsignacionPartido", back_populates="arbitro", lazy=True)

    def to_dict(self):
        return {"id": self.id, "nombre": self.nombre, "apellido": self.apellido, "telefono": self.telefono,
                "email": self.email, "activo": self.activo, "ciudad_origen_id": self.ciudad_origen_id,
                "ciudad_origen": self.ciudad_origen.to_dict() if self.ciudad_origen else None}


class Partido(db.Model):
    __tablename__ = "partidos"
    id = db.Column(db.Integer, primary_key=True)
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    estadio_cancha = db.Column(db.String(150), nullable=False)
    ciudad_juego_id = db.Column(db.Integer, db.ForeignKey("ciudades.id", ondelete="RESTRICT"), nullable=False)
    estado_partido = db.Column(db.String(30), nullable=False, default="Programado")
    ciudad_juego = db.relationship("Ciudad", back_populates="partidos")
    asignaciones = db.relationship("AsignacionPartido", back_populates="partido", lazy=True, cascade="all, delete-orphan")

    def to_dict(self, incluir_relaciones=True):
        datos = {"id": self.id, "fecha_hora": self.fecha_hora.isoformat(), "estadio_cancha": self.estadio_cancha,
                 "ciudad_juego_id": self.ciudad_juego_id, "estado_partido": self.estado_partido}
        if incluir_relaciones:
            datos["ciudad_juego"] = self.ciudad_juego.to_dict() if self.ciudad_juego else None
            cancha = UbicacionCancha.query.filter_by(nombre_cancha=self.estadio_cancha, ciudad_id=self.ciudad_juego_id).first()
            datos["ubicacion_cancha"] = cancha.to_dict() if cancha else None
            asignaciones = [a.to_dict(incluir_partido=False, incluir_detalle=True) for a in self.asignaciones]
            datos["asignaciones"] = asignaciones
            datos["arbitros_requeridos"] = ARBITROS_POR_PARTIDO
            datos["arbitros_asignados"] = len(asignaciones)
            datos["asignacion_completa"] = len(asignaciones) == ARBITROS_POR_PARTIDO
        return datos


class AsignacionPartido(db.Model):
    __tablename__ = "asignaciones_partido"
    __table_args__ = (db.UniqueConstraint("partido_id", "arbitro_id", name="uq_asignacion_partido_arbitro"),)
    id = db.Column(db.Integer, primary_key=True)
    partido_id = db.Column(db.Integer, db.ForeignKey("partidos.id", ondelete="CASCADE"), nullable=False)
    arbitro_id = db.Column(db.Integer, db.ForeignKey("arbitros.id", ondelete="RESTRICT"), nullable=False)
    estado_viaje = db.Column(db.String(40), nullable=False, default="Asignado")
    estado_pago = db.Column(db.String(30), nullable=False, default="Pendiente")
    costo_traslado_externo = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_traslado_interno = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_estadia = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_viaticos = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    fecha_salida = db.Column(db.DateTime)
    fecha_llegada_ciudad = db.Column(db.DateTime)
    fecha_llegada_estadio = db.Column(db.DateTime)
    fecha_fin_partido = db.Column(db.DateTime)
    fecha_salida_regreso = db.Column(db.DateTime)
    fecha_llegada_regreso = db.Column(db.DateTime)
    partido = db.relationship("Partido", back_populates="asignaciones")
    arbitro = db.relationship("Arbitro", back_populates="asignaciones")
    traslados = db.relationship("Traslado", back_populates="asignacion", cascade="all, delete-orphan")
    hospedaje = db.relationship("Hospedaje", back_populates="asignacion", uselist=False, cascade="all, delete-orphan")
    pago = db.relationship("Pago", back_populates="asignacion", uselist=False, cascade="all, delete-orphan")
    detalle_costos = db.relationship("DetalleCostoAsignacion", back_populates="asignacion", uselist=False, cascade="all, delete-orphan")
    eventos = db.relationship("EventoNotificacion", back_populates="asignacion", cascade="all, delete-orphan")

    def to_dict(self, incluir_partido=True, incluir_detalle=False):
        datos = {"id": self.id, "partido_id": self.partido_id, "arbitro_id": self.arbitro_id,
                 "estado_viaje": self.estado_viaje, "estado_pago": self.estado_pago,
                 "costo_traslado_externo": _numero(self.costo_traslado_externo), "costo_traslado_interno": _numero(self.costo_traslado_interno),
                 "costo_estadia": _numero(self.costo_estadia), "costo_viaticos": _numero(self.costo_viaticos), "costo_total": _numero(self.costo_total),
                 "arbitro": self.arbitro.to_dict() if self.arbitro else None}
        for campo in ("fecha_salida", "fecha_llegada_ciudad", "fecha_llegada_estadio", "fecha_fin_partido", "fecha_salida_regreso", "fecha_llegada_regreso"):
            valor = getattr(self, campo)
            datos[campo] = valor.isoformat() if valor else None
        if incluir_partido:
            datos["partido"] = self.partido.to_dict(False) if self.partido else None
        if incluir_detalle:
            datos["traslados"] = [traslado.to_dict() for traslado in self.traslados]
            datos["hospedaje"] = self.hospedaje.to_dict() if self.hospedaje else None
            datos["pago"] = self.pago.to_dict() if self.pago else None
            datos["detalle_costos"] = self.detalle_costos.to_dict() if self.detalle_costos else None
            externo = next((traslado for traslado in self.traslados if traslado.tipo == "externo" and traslado.sentido == "ida"), None)
            if self.arbitro and self.partido:
                from .services.travel import calcular_tiempo_traslado, distancia_entre, planificar_logistica, ruta_aerea
                distancia = distancia_entre(self.arbitro.ciudad_origen_id, self.partido.ciudad_juego_id)
                medio = externo.medio if externo else "local"
                ruta = ruta_aerea(self.arbitro.ciudad_origen.estado_id, self.partido.ciudad_juego.estado_id) if medio == "avion" else None
                distancia_estimacion = ruta["distancia_aerea_km"] if ruta else distancia
                datos["tiempo_traslado"] = calcular_tiempo_traslado(distancia_estimacion, medio, self.fecha_salida)
                datos["tiempo_traslado"]["distancia_vial_km"] = distancia
                datos["tiempo_traslado"]["ruta_aerea"] = ruta
                datos["plan_logistico"] = planificar_logistica(self.partido.fecha_hora, distancia_estimacion, medio, externo is not None)
        return datos


class DetalleCostoAsignacion(db.Model):
    """Snapshot de cantidades y tarifas usadas para el cálculo de la asignación."""
    __tablename__ = "detalle_costos_asignacion"
    id = db.Column(db.Integer, primary_key=True)
    asignacion_id = db.Column(db.Integer, db.ForeignKey("asignaciones_partido.id", ondelete="CASCADE"), nullable=False, unique=True)
    cantidad_noches = db.Column(db.Integer, nullable=False, default=0)
    costo_hospedaje_por_noche = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    cantidad_dias_viaticos = db.Column(db.Integer, nullable=False, default=1)
    viatico_por_dia = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_externo_por_trayecto = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_interno_por_trayecto = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    medio_externo = db.Column(db.String(20))
    asignacion = db.relationship("AsignacionPartido", back_populates="detalle_costos")

    def to_dict(self):
        return {
            "cantidad_noches": self.cantidad_noches,
            "costo_hospedaje_por_noche": _numero(self.costo_hospedaje_por_noche),
            "cantidad_dias_viaticos": self.cantidad_dias_viaticos,
            "viatico_por_dia": _numero(self.viatico_por_dia),
            "costo_externo_por_trayecto": _numero(self.costo_externo_por_trayecto),
            "costo_interno_por_trayecto": _numero(self.costo_interno_por_trayecto),
            "medio_externo": self.medio_externo,
        }


class Traslado(db.Model):
    __tablename__ = "traslados"
    id = db.Column(db.Integer, primary_key=True)
    asignacion_id = db.Column(db.Integer, db.ForeignKey("asignaciones_partido.id", ondelete="CASCADE"), nullable=False)
    sentido = db.Column(db.String(10), nullable=False)  # ida o vuelta
    tipo = db.Column(db.String(10), nullable=False)  # externo o interno
    medio = db.Column(db.String(20), nullable=False)
    origen = db.Column(db.String(200), nullable=False)
    destino = db.Column(db.String(200), nullable=False)
    costo = db.Column(db.Numeric(10, 2), nullable=False)
    fecha_hora = db.Column(db.DateTime)
    asignacion = db.relationship("AsignacionPartido", back_populates="traslados")

    def to_dict(self):
        return {"id": self.id, "sentido": self.sentido, "tipo": self.tipo, "medio": self.medio,
                "origen": self.origen, "destino": self.destino, "costo": _numero(self.costo),
                "fecha_hora": self.fecha_hora.isoformat() if self.fecha_hora else None}


class Hospedaje(db.Model):
    __tablename__ = "hospedajes"
    id = db.Column(db.Integer, primary_key=True)
    asignacion_id = db.Column(db.Integer, db.ForeignKey("asignaciones_partido.id", ondelete="CASCADE"), nullable=False, unique=True)
    hotel = db.Column(db.String(150))
    direccion = db.Column(db.String(250))
    check_in = db.Column(db.DateTime)
    check_out = db.Column(db.DateTime)
    noches = db.Column(db.Integer, nullable=False, default=0)
    costo_noche = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    costo_total = db.Column(db.Numeric(10, 2), nullable=False, default=0)
    asignacion = db.relationship("AsignacionPartido", back_populates="hospedaje")

    def to_dict(self):
        return {"id": self.id, "hotel": self.hotel, "direccion": self.direccion,
                "check_in": self.check_in.isoformat() if self.check_in else None,
                "check_out": self.check_out.isoformat() if self.check_out else None,
                "noches": self.noches, "costo_noche": _numero(self.costo_noche),
                "costo_total": _numero(self.costo_total)}


class Pago(db.Model):
    __tablename__ = "pagos"
    id = db.Column(db.Integer, primary_key=True)
    asignacion_id = db.Column(db.Integer, db.ForeignKey("asignaciones_partido.id", ondelete="CASCADE"), nullable=False, unique=True)
    monto_total = db.Column(db.Numeric(10, 2), nullable=False)
    estado = db.Column(db.String(30), nullable=False, default="Pendiente")
    fecha_pago = db.Column(db.DateTime)
    referencia = db.Column(db.String(100))
    asignacion = db.relationship("AsignacionPartido", back_populates="pago")

    def to_dict(self):
        return {"id": self.id, "monto_total": _numero(self.monto_total), "estado": self.estado,
                "fecha_pago": self.fecha_pago.isoformat() if self.fecha_pago else None,
                "referencia": self.referencia}


class EventoNotificacion(db.Model):
    __tablename__ = "eventos_notificacion"
    id = db.Column(db.Integer, primary_key=True)
    asignacion_id = db.Column(db.Integer, db.ForeignKey("asignaciones_partido.id", ondelete="CASCADE"), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    canal = db.Column(db.String(30), nullable=False, default="email")
    destinatario = db.Column(db.String(150), nullable=False)
    estado_envio = db.Column(db.String(30), nullable=False, default="Pendiente")
    fecha_hora = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    asignacion = db.relationship("AsignacionPartido", back_populates="eventos")
