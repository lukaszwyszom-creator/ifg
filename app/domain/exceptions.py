from app.core.exceptions import AppError


class InvalidInvoiceError(AppError):
    status_code = 422
    code = "invalid_invoice"


class NoKSeFSessionError(InvalidInvoiceError):
    """Brak aktywnej sesji KSeF — faktura nie może zostać wysłana."""
    code = "no_ksef_session"


class KSeFNotConnectedError(InvalidInvoiceError):
    """KSeF nie jest aktualnie osiągalny lub nie ma ważnej sesji."""
    code = "ksef_not_connected"


class InvalidStatusTransitionError(AppError):
    status_code = 409
    code = "invalid_status_transition"


class InsufficientStockError(AppError):
    """Próba rozchodu przekraczającego dostępny stan magazynowy."""
    status_code = 422
    code = "insufficient_stock"


class InvalidWarehouseDocumentError(AppError):
    """Błąd domenowy dokumentu magazynowego (nieprawidłowe dane, brakujące ceny)."""
    status_code = 422
    code = "invalid_warehouse_document"
