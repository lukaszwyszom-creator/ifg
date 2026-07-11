from enum import StrEnum


class UserRole(StrEnum):
    OPERATOR = "operator"
    ADMINISTRATOR = "administrator"


class ContractorSource(StrEnum):
    REGON = "regon"
    MANUAL = "manual"
    REGON_WITH_OVERRIDE = "regon_with_override"


class ContractorLookupStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    NOT_FOUND = "not_found"


class InvoiceStatus(StrEnum):
    READY_FOR_SUBMISSION = "ready_for_submission"
    SENDING = "sending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class InvoiceType(StrEnum):
    """Rodzaj faktury zgodny z polem RodzajFaktury w FA(3)."""
    VAT = "VAT"           # Faktura VAT standardowa
    KOR = "KOR"           # Faktura korygująca
    ZAL = "ZAL"           # Faktura zaliczkowa
    ROZ = "ROZ"           # Faktura rozliczająca
    UPR = "UPR"           # Faktura uproszczona (≤450 zł)
    KOR_ZAL = "KOR_ZAL"   # Korekta faktury zaliczkowej
    KOR_ROZ = "KOR_ROZ"   # Korekta faktury rozliczającej


class CorrectionType(StrEnum):
    """Zakres korekty faktury."""
    FULL = "full"       # korekta zerująca wszystkie pozycje (storno)
    PARTIAL = "partial" # korekta wybranych pozycji lub wartości


class InvoicePaymentStatus(StrEnum):
    UNPAID = "unpaid"
    PARTIALLY_PAID = "partially_paid"
    PAID = "paid"


class PaymentMethod(StrEnum):
    """Sposób płatności na fakturze sprzedaży (mapowanie FA(3) FormaPlatnosci)."""
    CASH = "cash"           # 1 — gotówka
    TRANSFER = "transfer"   # 6 — przelew


class PaymentMatchStatus(StrEnum):
    UNMATCHED = "unmatched"
    MATCHED = "matched"
    PARTIAL = "partial"
    MANUAL_REVIEW = "manual_review"


class PaymentMatchMethod(StrEnum):
    AUTO = "auto"
    MANUAL = "manual"
    CASH = "cash"


class TransmissionStatus(StrEnum):
    QUEUED = "queued"                    # utworzono job, oczekuje na worker
    PROCESSING = "processing"            # worker pobral zadanie i buduje XML
    SUBMITTED = "submitted"              # XML przyjety przez API KSeF, oczekujemy na potwierdzenie
    WAITING_STATUS = "waiting_status"    # polling odpytuje KSeF, wynik jeszcze nieznany
    SUCCESS = "success"                  # KSeF potwierdzil przyjecie faktury (kod 200)
    FAILED_TEMPORARY = "failed_temporary"  # blad przejsciowy, retry zaplanowany automatycznie
    FAILED_RETRYABLE = "failed_retryable"  # blad przejsciowy, oczekuje na reczny retry
    FAILED_PERMANENT = "failed_permanent"  # blad trwaly (blad mapowania, odrzucenie przez KSeF)


class KSeFOperationType(StrEnum):
    SALE_SEND = "SALE_SEND"
    SALE_STATUS = "SALE_STATUS"
    UPO_DOWNLOAD = "UPO_DOWNLOAD"
    SESSION_OPEN = "SESSION_OPEN"
    SESSION_CLOSE = "SESSION_CLOSE"
    SESSION_REFRESH = "SESSION_REFRESH"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SESSION_RENEWED = "SESSION_RENEWED"
    PURCHASE_SYNC_MANUAL = "PURCHASE_SYNC_MANUAL"
    PURCHASE_SYNC_AUTO = "PURCHASE_SYNC_AUTO"
    PURCHASE_METADATA_FETCH = "PURCHASE_METADATA_FETCH"
    PURCHASE_INVOICE_FETCH = "PURCHASE_INVOICE_FETCH"
    PURCHASE_IMPORT_SUMMARY = "PURCHASE_IMPORT_SUMMARY"
    PURCHASE_SYNC_EMAIL = "PURCHASE_SYNC_EMAIL"
    RETRY = "RETRY"
    RESUME = "RESUME"
    ERROR = "ERROR"
    SCHEDULER_STARTED = "SCHEDULER_STARTED"
    SCHEDULER_TICK = "SCHEDULER_TICK"
    SCHEDULER_SLOT = "SCHEDULER_SLOT"
    SCHEDULER_ENQUEUE = "SCHEDULER_ENQUEUE"
    SCHEDULER_SKIP_ALREADY_EXECUTED = "SCHEDULER_SKIP_ALREADY_EXECUTED"
    SCHEDULER_RECOVERY = "SCHEDULER_RECOVERY"
    SCHEDULER_DISABLED = "SCHEDULER_DISABLED"
    SCHEDULER_INVALID_CRON = "SCHEDULER_INVALID_CRON"


class KSeFSeverity(StrEnum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"


class JobStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


# ── Magazyn v1 ────────────────────────────────────────────────────────────────

class WarehouseItemType(StrEnum):
    GOODS = "goods"       # towar — wpływa na stan magazynowy
    SERVICE = "service"   # usługa — nie wpływa na stan


class WarehouseDocumentType(StrEnum):
    PZ = "PZ"           # Przyjęcie Zewnętrzne
    WZ = "WZ"           # Wydanie Zewnętrzne
    KK = "KK"           # Korekta
    TRANSFER = "TRANSFER"  # ukryty w UI, dostępny w backendzie


class WarehouseDocumentStatus(StrEnum):
    DRAFT = "draft"
    POSTED = "posted"        # zaksięgowany — zmienił stany magazynowe
    CANCELLED = "cancelled"  # anulowany — historia zachowana, stan niezmieniany


class FiscalReportStatus(StrEnum):
    ENTERED_FOR_DISTRIBUTION = "entered_for_distribution"
    DISTRIBUTED = "distributed"
