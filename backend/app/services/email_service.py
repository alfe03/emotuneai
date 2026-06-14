import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

def send_email(to_email: str, subject: str, html_content: str):
    if not settings.SMTP_USERNAME or not settings.SMTP_PASSWORD:
        logger.warning(f"SMTP ayarları bulunamadığı için e-posta gönderilemedi: {to_email}")
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
    msg["To"] = to_email

    part = MIMEText(html_content, "html")
    msg.attach(part)

    try:
        if settings.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT)
        else:
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            server.starttls()
            
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
        server.quit()
        logger.info(f"E-posta başarıyla gönderildi: {to_email}")
    except Exception as e:
        logger.error(f"E-posta gönderilirken hata oluştu: {str(e)}")

def send_welcome_email(to_email: str, username: str):
    subject = "EmoTuneAI'a Hoş Geldiniz! 🎵"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #121212; color: #ffffff; padding: 30px; border-radius: 12px; text-align: center;">
          <h1 style="color: #1DB954;">EmoTuneAI</h1>
          <h2>Hoş Geldin, {username}!</h2>
          <p style="font-size: 16px; line-height: 1.5; color: #e0e0e0;">
            Aramıza katıldığın için çok mutluyuz. Ruh halini analiz edip sana en uygun müzikleri önermeye hazırız.
          </p>
          <p style="font-size: 16px; line-height: 1.5; color: #e0e0e0;">
            Hemen platforma dön ve müzik keşfine başla!
          </p>
          <a href="{settings.FRONTEND_URL}" style="display: inline-block; padding: 12px 24px; background-color: #1DB954; color: #ffffff; text-decoration: none; border-radius: 20px; font-weight: bold; margin-top: 20px;">
            Hemen Keşfet
          </a>
        </div>
      </body>
    </html>
    """
    send_email(to_email, subject, html_content)

def send_reset_password_email(to_email: str, reset_token: str):
    subject = "EmoTuneAI - Şifre Sıfırlama İsteği"
    reset_url = f"{settings.FRONTEND_URL}?reset_token={reset_token}"
    html_content = f"""
    <html>
      <body style="font-family: Arial, sans-serif; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #121212; color: #ffffff; padding: 30px; border-radius: 12px; text-align: center;">
          <h1 style="color: #1DB954;">EmoTuneAI</h1>
          <h2>Şifre Sıfırlama</h2>
          <p style="font-size: 16px; line-height: 1.5; color: #e0e0e0;">
            Hesabınız için bir şifre sıfırlama isteği aldık. Aşağıdaki butona tıklayarak yeni şifrenizi belirleyebilirsiniz.
          </p>
          <a href="{reset_url}" style="display: inline-block; padding: 12px 24px; background-color: #1DB954; color: #ffffff; text-decoration: none; border-radius: 20px; font-weight: bold; margin-top: 20px;">
            Şifremi Sıfırla
          </a>
          <p style="font-size: 14px; color: #888888; margin-top: 20px;">
            Eğer bu isteği siz yapmadıysanız bu e-postayı dikkate almayabilirsiniz.
          </p>
        </div>
      </body>
    </html>
    """
    send_email(to_email, subject, html_content)
