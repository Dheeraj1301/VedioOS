from decimal import Decimal

CURRENCY_SPECS = {
    "INR": {"symbol": "₹", "exponent": 2},
    "USD": {"symbol": "$", "exponent": 2},
    "EUR": {"symbol": "€", "exponent": 2},
    "GBP": {"symbol": "£", "exponent": 2},
    "JPY": {"symbol": "¥", "exponent": 0},
    "KRW": {"symbol": "₩", "exponent": 0},
}

CURRENCY_CHOICES = [("", "Choose currency"), *[(code, code) for code in CURRENCY_SPECS]]


def currency_exponent(currency):
    return CURRENCY_SPECS.get(currency, {}).get("exponent", 2)


def currency_symbol(currency):
    return CURRENCY_SPECS.get(currency, {}).get("symbol", currency or "")


def minor_to_major(amount_minor, currency):
    if amount_minor is None:
        return None
    exponent = currency_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    return (Decimal(amount_minor) / (10**exponent)).quantize(quantum)


def major_to_minor(amount, currency):
    exponent = currency_exponent(currency)
    quantum = Decimal(1).scaleb(-exponent)
    if amount != amount.quantize(quantum):
        if exponent == 0:
            raise ValueError(f"{currency} does not support decimals.")
        raise ValueError(f"{currency} supports up to {exponent} decimal places.")
    return int(amount * (10**exponent))


def format_money(amount_minor, currency):
    if amount_minor is None:
        return "Not configured"
    exponent = currency_exponent(currency)
    amount = minor_to_major(amount_minor, currency)
    return f"{currency_symbol(currency)}{amount:,.{exponent}f}"
