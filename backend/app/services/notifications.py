"""Registro y entrega de avisos por email al administrador."""

import os
import smtplib
from email.message import EmailMessage

from ..models import EventoNotificacion


def registrar_y_enviar_evento(asignacion, tipo: str) -> EventoNotificacion:
    destinatario = os.getenv("ADMIN_EMAIL", "")
    evento = EventoNotificacion(asignacion=asignacion, tipo=tipo, destinatario=destinatario,
                                estado_envio="Pendiente")
    host = os.getenv("SMTP_HOST", "")
    if not host or not destinatario:
        return evento
    mensaje = EmailMessage()
    mensaje["Subject"] = f"Liga de baloncesto: {tipo}"
    mensaje["From"] = os.getenv("SMTP_USER") or destinatario
    mensaje["To"] = destinatario
    mensaje.set_content(f"Se registró el evento '{tipo}' para la asignación #{asignacion.id}.")
    try:
        with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=10) as servidor:
            if os.getenv("SMTP_USE_TLS", "true").lower() == "true":
                servidor.starttls()
            usuario, clave = os.getenv("SMTP_USER", ""), os.getenv("SMTP_PASSWORD", "")
            if usuario:
                servidor.login(usuario, clave)
            servidor.send_message(mensaje)
        evento.estado_envio = "Enviado"
    except (OSError, smtplib.SMTPException):
        evento.estado_envio = "Error"
    return evento
