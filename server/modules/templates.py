"""Message templates for the communications hub (plan-11).

Spanish-first, with English and Portuguese fallbacks (matching the PWA i18n set).
Each template is keyed by ``name`` then locale and carries a ``subject`` (used by
email/push title), a plaintext ``body`` (SMS / push body / email text part) and
an optional ``html`` part (email only).

Rendering is deliberately tiny: ``{variable}`` placeholders filled from a dict.
We use ``str.format_map`` with a default-empty mapping so a missing variable
renders as an empty string instead of raising — a crisis notification should
never fail to send because one optional field was absent.
"""

from typing import Optional

DEFAULT_LOCALE = "es"
SUPPORTED_LOCALES = ("es", "en", "pt")


class _Default(dict):
    """dict whose missing keys render as ''. Used by str.format_map."""

    def __missing__(self, key):  # noqa: D401 - format hook
        return ""


# TEMPLATES[name][locale] = {subject, body, html?}
TEMPLATES: dict = {
    # An inbound report about a person was received and recorded.
    "report_received": {
        "es": {
            "subject": "EGI: recibimos tu reporte",
            "body": "Recibimos tu reporte sobre {person_name}. Lo estamos revisando. Gracias por ayudar.",
        },
        "en": {
            "subject": "EGI: we received your report",
            "body": "We received your report about {person_name}. We are reviewing it. Thank you for helping.",
        },
        "pt": {
            "subject": "EGI: recebemos o seu relato",
            "body": "Recebemos o seu relato sobre {person_name}. Estamos a analisá-lo. Obrigado por ajudar.",
        },
    },
    # A person's status changed (e.g. missing -> found).
    "status_changed": {
        "es": {
            "subject": "EGI: cambio de estado",
            "body": "El estado de {person_name} cambió a: {status}. Operación: {operation_name}.",
        },
        "en": {
            "subject": "EGI: status update",
            "body": "The status of {person_name} changed to: {status}. Operation: {operation_name}.",
        },
        "pt": {
            "subject": "EGI: atualização de estado",
            "body": "O estado de {person_name} mudou para: {status}. Operação: {operation_name}.",
        },
    },
    # Ask the reporter for more information about a person.
    "request_info": {
        "es": {
            "subject": "EGI: necesitamos más datos",
            "body": "Necesitamos más datos sobre {person_name}. Responde a este mensaje con lo que sepas (lugar, ropa, contacto).",
        },
        "en": {
            "subject": "EGI: more info needed",
            "body": "We need more information about {person_name}. Reply to this message with anything you know (location, clothes, contact).",
        },
        "pt": {
            "subject": "EGI: precisamos de mais dados",
            "body": "Precisamos de mais dados sobre {person_name}. Responda a esta mensagem com o que souber (local, roupa, contacto).",
        },
    },
    # Operation-wide broadcast / alert.
    "alert": {
        "es": {
            "subject": "EGI alerta: {operation_name}",
            "body": "{title}\n\n{body}",
            "html": "<h2>{title}</h2><p>{body}</p><p><small>Operación: {operation_name}</small></p>",
        },
        "en": {
            "subject": "EGI alert: {operation_name}",
            "body": "{title}\n\n{body}",
            "html": "<h2>{title}</h2><p>{body}</p><p><small>Operation: {operation_name}</small></p>",
        },
        "pt": {
            "subject": "EGI alerta: {operation_name}",
            "body": "{title}\n\n{body}",
            "html": "<h2>{title}</h2><p>{body}</p><p><small>Operação: {operation_name}</small></p>",
        },
    },
    # Welcome email for a new account.
    "welcome": {
        "es": {
            "subject": "Bienvenido a EGI",
            "body": "Hola {name}, tu cuenta EGI ya está activa. Rol: {role}.",
            "html": "<p>Hola {name},</p><p>Tu cuenta EGI ya está activa. Rol: <b>{role}</b>.</p>",
        },
        "en": {
            "subject": "Welcome to EGI",
            "body": "Hi {name}, your EGI account is active. Role: {role}.",
            "html": "<p>Hi {name},</p><p>Your EGI account is active. Role: <b>{role}</b>.</p>",
        },
        "pt": {
            "subject": "Bem-vindo ao EGI",
            "body": "Olá {name}, a sua conta EGI está ativa. Função: {role}.",
            "html": "<p>Olá {name},</p><p>A sua conta EGI está ativa. Função: <b>{role}</b>.</p>",
        },
    },
    # Password reset email. {reset_url} or {token} provided by the caller.
    "password_reset": {
        "es": {
            "subject": "EGI: restablecer contraseña",
            "body": "Para restablecer tu contraseña usa este enlace: {reset_url}\nSi no fuiste tú, ignora este mensaje. Caduca en {expires_minutes} minutos.",
            "html": "<p>Para restablecer tu contraseña haz clic: <a href=\"{reset_url}\">restablecer</a>.</p><p>Si no fuiste tú, ignora este mensaje. Caduca en {expires_minutes} minutos.</p>",
        },
        "en": {
            "subject": "EGI: reset your password",
            "body": "Use this link to reset your password: {reset_url}\nIf this wasn't you, ignore this message. Expires in {expires_minutes} minutes.",
            "html": "<p>Click to reset your password: <a href=\"{reset_url}\">reset</a>.</p><p>If this wasn't you, ignore this message. Expires in {expires_minutes} minutes.</p>",
        },
        "pt": {
            "subject": "EGI: redefinir palavra-passe",
            "body": "Use este link para redefinir a sua palavra-passe: {reset_url}\nSe não foi você, ignore esta mensagem. Expira em {expires_minutes} minutos.",
            "html": "<p>Clique para redefinir: <a href=\"{reset_url}\">redefinir</a>.</p><p>Se não foi você, ignore. Expira em {expires_minutes} minutos.</p>",
        },
    },
}


def template_exists(name: str) -> bool:
    return name in TEMPLATES


def _resolve_locale(name: str, locale: Optional[str]) -> str:
    locales = TEMPLATES.get(name, {})
    if locale and locale in locales:
        return locale
    if DEFAULT_LOCALE in locales:
        return DEFAULT_LOCALE
    # First defined locale as a last resort.
    return next(iter(locales), DEFAULT_LOCALE)


def render(name: str, variables: Optional[dict] = None, locale: Optional[str] = None) -> dict:
    """Render a template to ``{subject, body, html}``.

    Raises ``KeyError`` if the template name is unknown. Missing variables render
    as empty strings (never raises on a missing field).
    """
    if name not in TEMPLATES:
        raise KeyError(f"unknown template: {name}")
    loc = _resolve_locale(name, locale)
    tmpl = TEMPLATES[name][loc]
    data = _Default(variables or {})
    out = {
        "subject": tmpl.get("subject", "").format_map(data),
        "body": tmpl.get("body", "").format_map(data),
        "locale": loc,
    }
    if tmpl.get("html"):
        out["html"] = tmpl["html"].format_map(data)
    return out
