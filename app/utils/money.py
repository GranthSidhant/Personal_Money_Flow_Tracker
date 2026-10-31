from decimal import Decimal, ROUND_HALF_UP
from typing import Union


def rupees_to_paise(amount: Union[int, float, str, Decimal]) -> int:
    """
    Safely convert rupee amounts to integer paise using Decimal to prevent
    binary floating-point precision loss.
    """
    if amount is None or amount == "":
        return 0
    d = Decimal(str(amount).strip())
    # 1 Rupee = 100 Paise
    return int((d * Decimal("100")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise to Decimal rupees."""
    if paise is None:
        return Decimal("0.00")
    return (Decimal(paise) / Decimal("100")).quantize(Decimal("0.01"))


def format_inr(paise: int, include_symbol: bool = True) -> str:
    """
    Format paise amount into Indian Rupee formatting (e.g., ₹1,23,456.00 or ₹24,500).
    """
    if paise is None:
        paise = 0
    
    is_negative = paise < 0
    abs_paise = abs(paise)
    rupees_part = abs_paise // 100
    paise_part = abs_paise % 100
    
    s = str(rupees_part)
    if len(s) > 3:
        # Indian number formatting: last 3 digits, then groups of 2
        last_three = s[-3:]
        remaining = s[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_rupees = ",".join(groups) + "," + last_three
    else:
        formatted_rupees = s

    formatted = f"{formatted_rupees}.{paise_part:02d}" if paise_part > 0 else formatted_rupees
    
    prefix = "-" if is_negative else ""
    symbol = "₹" if include_symbol else ""
    return f"{prefix}{symbol}{formatted}"
