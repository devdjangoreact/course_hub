import logging
import smtplib
from email.message import EmailMessage

logger = logging.getLogger(__name__)


class SmtpMailer:
    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        password: str,
        from_addr: str,
        use_tls: bool = True,
    ) -> None:
        self._host = host
        self._port = port
        self._username = username
        self._password = password
        self._from = from_addr
        self._use_tls = use_tls

    @property
    def enabled(self) -> bool:
        return bool(self._host and self._from)

    def send(self, to: str, subject: str, body: str) -> None:
        if not self.enabled:
            logger.info("SMTP disabled; skip email to %s", to)
            return
        msg = EmailMessage()
        msg["From"] = self._from
        msg["To"] = to
        msg["Subject"] = subject
        msg.set_content(body)
        with smtplib.SMTP(self._host, self._port, timeout=30) as smtp:
            if self._use_tls:
                smtp.starttls()
            if self._username:
                smtp.login(self._username, self._password)
            smtp.send_message(msg)
