import smtplib, ssl

class MailClient:
    def __init__(self, server, ssl_port, username, password, sender):
        self.server = server
        self.ssl_port = ssl_port
        self.username = username
        self.password = password
        self.sender = sender

    def send_mail(self, recipient, subject, message):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)

        with smtplib.SMTP_SSL(self.server, self.ssl_port, context=context) as mail_server:
            mail_server.login(self.username, self.password)
            mail_server.sendmail(self.sender, recipient, f"Subject: {subject}\n\n{message}")
