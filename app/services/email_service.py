"""
Serviço de envio de e-mail (confirmação de cadastro e recuperação de senha).

Usa SMTP puro (smtplib, biblioteca padrão do Python) — funciona com qualquer
provedor SMTP, incluindo o tier gratuito da Brevo (300 e-mails/dia, sem
cartão de crédito): https://www.brevo.com

Os templates HTML usam fundo claro (não o tema escuro do app): é a prática
recomendada para e-mail, já que muitos clientes de e-mail não respeitam bem
fundos escuros customizados. A identidade visual (logo "dumpai", cor de
destaque teal, fonte monoespaçada no logo) é mantida.
"""
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.config import settings

ACCENT = "#0d9488"       # teal, mesma família da cor de destaque do app
BG = "#f4f6f8"
CARD_BG = "#ffffff"
TEXT = "#1f2937"
TEXT_DIM = "#6b7280"
BORDER = "#e5e7eb"


def _base_template(title: str, body_html: str, preheader: str = "") -> str:
    return f"""\
<!DOCTYPE html>
<html lang="pt-br">
<head><meta charset="UTF-8"><title>{title}</title></head>
<body style="margin:0; padding:0; background:{BG}; font-family: -apple-system, Segoe UI, Arial, sans-serif;">
  <span style="display:none; max-height:0; overflow:hidden;">{preheader}</span>
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{BG}; padding: 32px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="480" cellpadding="0" cellspacing="0"
               style="background:{CARD_BG}; border:1px solid {BORDER}; border-radius:10px; overflow:hidden;">
          <tr>
            <td style="padding: 28px 32px 0 32px;">
              <div style="font-family: 'Courier New', monospace; font-weight:700; font-size:20px; color:{TEXT};">
                dump<span style="color:{ACCENT};">ai</span>
              </div>
            </td>
          </tr>
          <tr>
            <td style="padding: 20px 32px 32px 32px; color:{TEXT}; font-size:15px; line-height:1.6;">
              {body_html}
            </td>
          </tr>
        </table>
        <div style="color:{TEXT_DIM}; font-size:12px; margin-top:16px;">
          DumpAI — plataforma de estudo para certificações técnicas.
        </div>
      </td>
    </tr>
  </table>
</body>
</html>
"""


def _send(to_email: str, subject: str, html_body: str) -> None:
    if not settings.SMTP_HOST:
        raise RuntimeError(
            "SMTP não configurado. Defina SMTP_HOST/SMTP_USER/SMTP_PASSWORD no .env."
        )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to_email
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
        if settings.SMTP_USE_TLS:
            server.starttls(context=context)
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.sendmail(settings.EMAIL_FROM, [to_email], msg.as_string())


def send_verification_email(to_email: str, username: str, verify_url: str) -> None:
    body = f"""
      <p>Olá, <b>{username}</b>!</p>
      <p>Falta só um passo para confirmar sua conta no DumpAI.</p>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 24px 0;">
        <tr>
          <td style="background:{ACCENT}; border-radius:6px;">
            <a href="{verify_url}" target="_blank"
               style="display:inline-block; padding:12px 24px; color:#ffffff; text-decoration:none;
                      font-weight:600; font-family: 'Courier New', monospace;">
              Confirmar meu e-mail
            </a>
          </td>
        </tr>
      </table>
      <p style="color:{TEXT_DIM}; font-size:13px;">
        Se o botão não funcionar, copie e cole este link no navegador:<br>
        <span style="word-break:break-all;">{verify_url}</span>
      </p>
      <p style="color:{TEXT_DIM}; font-size:13px;">
        Este link expira em {settings.EMAIL_VERIFICATION_EXPIRE_MINUTES // 60} horas.
        Se você não criou essa conta, pode ignorar este e-mail.
      </p>
    """
    _send(
        to_email,
        "Confirme seu cadastro no DumpAI",
        _base_template("Confirme seu cadastro", body, preheader="Confirme seu e-mail para ativar sua conta."),
    )


def send_password_reset_code_email(to_email: str, username: str, code: str) -> None:
    body = f"""
      <p>Olá, <b>{username}</b>!</p>
      <p>Recebemos um pedido para recuperar sua senha no DumpAI. Use o código abaixo para confirmar que é você:</p>
      <div style="margin: 24px 0; text-align:center;">
        <span style="display:inline-block; padding: 14px 28px; background:{BG}; border:1px dashed {ACCENT};
                     border-radius:8px; font-family:'Courier New', monospace; font-size:28px; font-weight:700;
                     letter-spacing: 6px; color:{TEXT};">
          {code}
        </span>
      </div>
      <p style="color:{TEXT_DIM}; font-size:13px;">
        Esse código expira em {settings.PASSWORD_RESET_CODE_EXPIRE_MINUTES} minutos.
        Se você não pediu a recuperação de senha, ignore este e-mail — sua conta continua segura.
      </p>
    """
    _send(
        to_email,
        f"Seu código de verificação: {code}",
        _base_template("Código de recuperação de senha", body, preheader="Use este código para recuperar sua senha."),
    )


def send_temp_password_email(to_email: str, username: str, temp_password: str, login_url: str) -> None:
    body = f"""
      <p>Olá, <b>{username}</b>!</p>
      <p>Confirmamos sua identidade. Geramos uma <b>senha temporária nova</b> para você entrar
      (por segurança, nunca reenviamos sua senha original):</p>
      <div style="margin: 24px 0; text-align:center;">
        <span style="display:inline-block; padding: 14px 28px; background:{BG}; border:1px dashed {ACCENT};
                     border-radius:8px; font-family:'Courier New', monospace; font-size:22px; font-weight:700;
                     color:{TEXT};">
          {temp_password}
        </span>
      </div>
      <table role="presentation" cellpadding="0" cellspacing="0" style="margin: 8px 0 24px 0;">
        <tr>
          <td style="background:{ACCENT}; border-radius:6px;">
            <a href="{login_url}" target="_blank"
               style="display:inline-block; padding:12px 24px; color:#ffffff; text-decoration:none;
                      font-weight:600; font-family: 'Courier New', monospace;">
              Entrar agora
            </a>
          </td>
        </tr>
      </table>
      <p style="color:{TEXT_DIM}; font-size:13px;">
        Assim que entrar, recomendamos trocar essa senha temporária por uma de sua escolha
        (em "Minha conta &rarr; Trocar senha").
      </p>
    """
    _send(
        to_email,
        "Sua nova senha temporária — DumpAI",
        _base_template("Sua senha temporária", body, preheader="Sua senha temporária para acessar o DumpAI."),
    )
