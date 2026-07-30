from app.infrastructure.email.smtp_mailer import SmtpMailer


class DeliveryMailer:
    def __init__(self, mailer: SmtpMailer) -> None:
        self._mailer = mailer

    def send_paid_course(
        self,
        to: str,
        course_name: str,
        download_url: str,
        invite: str | None,
    ) -> None:
        lines = [
            f"Your order for «{course_name}» is paid.",
            "",
            f"Download: {download_url}",
        ]
        if invite:
            lines.extend(["", f"Private channel invite: {invite}"])
        self._mailer.send(
            to=to,
            subject=f"Course Hub: {course_name}",
            body="\n".join(lines),
        )

    def send_promo(self, to: str, course_name: str, short_description: str) -> None:
        self._mailer.send(
            to=to,
            subject=f"Course Hub promo: {course_name}",
            body=f"{course_name}\n\n{short_description}",
        )
