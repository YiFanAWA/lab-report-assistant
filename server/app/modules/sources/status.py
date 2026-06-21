"""来源与证据侧枚举。"""

from enum import Enum


class SourceKind(str, Enum):
    PUBLIC_URL = "PUBLIC_URL"
    LOCAL_FILE = "LOCAL_FILE"


class SourceType(str, Enum):
    WEB_PAGE = "WEB_PAGE"
    PDF = "PDF"
    DOCX = "DOCX"
    TXT = "TXT"
    CSV = "CSV"
    EXCEL = "EXCEL"
    UNKNOWN = "UNKNOWN"


class CollectionStatus(str, Enum):
    REGISTERED = "REGISTERED"
    FETCHED = "FETCHED"
    PARSED = "PARSED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class ParserType(str, Enum):
    HTML_TEXT = "HTML_TEXT"
    PDF_TEXT = "PDF_TEXT"
    DOCX_TEXT = "DOCX_TEXT"
    TXT_TEXT = "TXT_TEXT"


class ParseStatus(str, Enum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    UNSUPPORTED = "UNSUPPORTED"


class EvidenceStatus(str, Enum):
    CANDIDATE = "CANDIDATE"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class EvidenceType(str, Enum):
    BACKGROUND = "BACKGROUND"
    METHOD = "METHOD"
    DATA_SOURCE = "DATA_SOURCE"
    METRIC = "METRIC"
    RESULT = "RESULT"
    LIMITATION = "LIMITATION"
    DEFINITION = "DEFINITION"
    REFERENCE = "REFERENCE"


class EvidenceCandidateSource(str, Enum):
    MODEL = "MODEL"
    LOCAL_RULE = "LOCAL_RULE"
    MANUAL = "MANUAL"
