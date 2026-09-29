from typing import Optional

from app.schemas.extraction import ExtractedInvoice

class ValidationResult:
    def __init__(
        self,
        is_valid: bool,
        status: str,
        errors: list[str],
    ):
        self.is_valid = is_valid
        self.status = status
        self.errors = errors

    
    def to_dict(self):
        return {
            "is_valid": self.is_valid,
            "status": self.status,
            "error": self.errors,
        }

    
def _close_enough(
    a: float,
    b: float,
    tolerance: float = 0.01,
) -> bool:
    return abs(a-b) <= tolerance


def validate_extraction(
    data: ExtractedInvoice,
) -> ValidationResult:
    errors = []

    # Check subtotal + tax = total
    if (
        data.subtotal is not None
        and data.tax is not None
        and data.total is not None
    ):
        expected_total = data.subtotal + data.tax

        if not _close_enough(
            expected_total,
            data.total,
        ):
            errors.append(
                f"Subtotal + tax does not equal total:"
                f"{data.subtotal} + {data.tax} != {data.total}"
            )

    # Check line item calculations
    for index, item in enumerate(data.items):
        if (
            item.quantity is not None
            and item.unit_price is not None
            and item.amount is not None
        ):

            expected_amount = (
                item.quantity * item.unit_price
            )

            if not _close_enough(
                expected_amount,
                item.amount,
            ):
                errors.append(
                    f"Item {index+1} amount mismatch: "
                    f"{item.quantity} x {item.unit_price} "
                    f"!= {item.amount}"
                )

    # Determine final status
    if errors:
        return ValidationResult(
            is_valid=False,
            status="FLAG_FOR_REVIEW",
            errors=errors,
        )

    return ValidationResult(
        is_valid=True,
        status="VALIDATED",
        errors = [],
    )
