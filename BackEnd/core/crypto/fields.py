import re


def normalize_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def mask_cpf(cpf: str) -> str:
    digits = normalize_digits(cpf)
    if len(digits) != 11:
        return "***"
    return f"***.{digits[3:6]}.{digits[6:9]}-**"


def mask_phone(phone: str) -> str:
    digits = normalize_digits(phone)
    if len(digits) < 4:
        return "****"
    return f"***-{digits[-4:]}"


def clean_str(value, max_len: int = 255) -> str:
    if value is None:
        return ""
    return str(value).strip()[:max_len]
