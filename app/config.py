import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    SESSION_SECRET: str = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./dumpai.db")
    QUESTIONS_PER_EVALUATION: int = int(os.getenv("QUESTIONS_PER_EVALUATION", "5"))


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
