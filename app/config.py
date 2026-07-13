import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./data/dumpai.db")
    QUESTIONS_PER_EVALUATION: int = int(os.getenv("QUESTIONS_PER_EVALUATION", "5"))

    # URL pública onde o app está acessível (usada nos links dos e-mails)
    APP_BASE_URL: str = os.getenv("APP_BASE_URL", "http://localhost:8000")

    # SMTP para envio de e-mails (confirmação de cadastro / recuperação de senha)
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "no-reply@dumpai.local")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "DumpAI")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")

    # Validade dos códigos/links de verificação, em minutos
    EMAIL_VERIFICATION_EXPIRE_MINUTES: int = 60 * 24  # 24h para confirmar cadastro
    PASSWORD_RESET_CODE_EXPIRE_MINUTES: int = 10       # 10min para o código de recuperação

    @property
    def EMAIL_CONFIGURED(self) -> bool:
        """
        True só se houver o mínimo necessário para enviar e-mail de verdade.
        Usado em todo o app para SINALIZAR (banners) e, no caso da recuperação
        de senha, para BLOQUEAR o fluxo em vez de fingir que funcionou.
        """
        return bool(self.SMTP_HOST and self.SMTP_USER and self.SMTP_PASSWORD)


settings = Settings()

# Níveis de progressão, em ordem
LEVELS = ["trainee", "junior", "pleno", "senior"]
LEVEL_LABELS = {
    "trainee": "Trainee",
    "junior": "Júnior",
    "pleno": "Pleno",
    "senior": "Sênior",
}

# Catálogo de linguagens/certificações
CERTIFICATIONS = {
    "java": {
        "label": "Java",
        "cert_name": "Oracle Certified Professional: Java SE Programmer (OCP)",
        "cert_url": "https://education.oracle.com/oracle-certified-professional-java-se-programmer",
        "notes": "Inclui também OCA (Oracle Certified Associate) como base para iniciantes.",
    },
    "angular": {
        "label": "Angular",
        "cert_name": "Angular Certification",
        "cert_url": "https://certificates.dev/angular",
        "notes": "Certificação criada por Google Developer Experts, com níveis Junior, Mid-Level e Senior.",
    },
    "sql": {
        "label": "SQL",
        "cert_name": "Oracle Database SQL Certified Associate",
        "cert_url": "https://education.oracle.com/oracle-database-sql-certified-associate",
        "notes": "Cobre SQL/PLSQL. Alternativa: Microsoft DP-900 (Azure Data Fundamentals).",
    },
    "git": {
        "label": "Git",
        "cert_name": "GitHub Foundations Certification",
        "cert_url": "https://www.credly.com/org/github/badge/github-foundations",
        "notes": "Certificação oficial do GitHub, cobre fundamentos de controle de versão.",
    },
    "python": {
        "label": "Python",
        "cert_name": "PCEP / PCAP (Python Institute)",
        "cert_url": "https://pythoninstitute.org/certification",
        "notes": "PCEP (Entry) e PCAP (Associate) são certificações estruturadas por nível.",
    },
}
