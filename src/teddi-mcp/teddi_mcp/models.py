"""Pydantic data models and enums for TEDDI search integration."""

from dataclasses import dataclass
from enum import StrEnum


class SearchIn(StrEnum):
    """Search scope: where to search for the term."""

    ABBREVIATIONS = "abbreviations"
    DEFINITIONS = "definitions"
    BOTH = "both"


class SearchPattern(StrEnum):
    """Search pattern: how to match the term."""

    ALL_OCCURRENCES = "alloccurrences"
    EXACT_MATCH = "exactmatch"
    STARTING_WITH = "startingwith"
    ENDING_WITH = "endingwith"


class TechnicalBody(StrEnum):
    """ETSI and standardization body identifiers."""

    ALL = "all"
    THREE_GPP = "3gpp"
    AERO = "aero"
    AFI = "afi"
    ARF = "arf"
    AT = "at"
    ATA = "ata"
    ATM = "atm"
    ATTM = "attm"
    BOARD = "board"
    BRAN = "bran"
    BROADCAS = "broadcas"
    BT = "bt"
    BTC = "btc"
    CABLE = "cable"
    CCM = "ccm"
    CDM = "cdm"
    CIM = "cim"
    CLOUD = "cloud"
    CN = "cn"
    CYBER = "cyber"
    DATA = "data"
    DECT = "dect"
    DTA = "dta"
    E2NA = "e2na"
    E4P = "e4p"
    EASI = "easi"
    ECI = "eci"
    ECMA = "ecma"
    ECMATC32 = "ecmatc32"
    EE = "ee"
    EHEALTH = "ehealth"
    EMTEL = "emtel"
    ENI = "eni"
    ERM = "erm"
    ESI = "esi"
    ETI = "eti"
    ETSI = "etsi"
    F5G = "f5g"
    GA = "ga"
    GRID = "grid"
    HF = "hf"
    ICC = "icc"
    IEEE = "ieee"
    IETF = "ietf"
    IMCC = "imcc"
    INS = "ins"
    INT = "int"
    IP6 = "ip6"
    IPE = "ipe"
    IPRC = "iprc"
    ISAC = "isac"
    ISI = "isi"
    ISM = "ism"
    ISO = "iso"
    ITS = "its"
    ITU = "itu"
    LI = "li"
    LIS = "lis"
    LTN = "ltn"
    M2M = "m2m"
    MAT = "mat"
    MBC = "mbc"
    MCD = "mcd"
    M_COMM = "m-comm"
    MEC = "mec"
    MESA = "mesa"
    MMG = "mmg"
    MOI = "moi"
    MSG = "msg"
    MTA = "mta"
    MTC = "mtc"
    MTS = "mts"
    MWT = "mwt"
    NA = "na"
    NFV = "nfv"
    NGP = "ngp"
    NIN = "nin"
    NTECH = "ntech"
    OCG = "ocg"
    OEU = "oeu"
    OMA = "oma"
    ONEM2M = "onem2m"
    ORI = "ori"
    OSG = "osg"
    OSM = "osm"
    PDL = "pdl"
    PLT = "plt"
    PS = "ps"
    PTS = "pts"
    QKD = "qkd"
    QSC = "qsc"
    RES = "res"
    RIS = "ris"
    RRS = "rrs"
    RT = "rt"
    SAFETY = "safety"
    SAGE = "sage"
    SAI = "sai"
    SCP = "scp"
    SEC = "sec"
    SES = "ses"
    SET = "set"
    SMARTBAN = "smartban"
    SMARTM2M = "smartm2m"
    SMG = "smg"
    SMT = "smt"
    SPAN = "span"
    SPS = "sps"
    STQ = "stq"
    TCCE = "tcce"
    TE = "te"
    TETRA = "tetra"
    THZ = "thz"
    TIPHON = "tiphon"
    TISPAN = "tispan"
    TM = "tm"
    TMN = "tmn"
    TRAC = "trac"
    UMTS = "umts"
    USER = "user"
    ZSM = "zsm"


class OutputFormat(StrEnum):
    """Supported CLI output formats."""

    TABLE = "table"
    JSON = "json"
    ISON = "ison"
    TOON = "toon"


@dataclass
class DocumentRef:
    """Reference to a specification document from TEDDI results."""

    technical_body: str
    """Technical body that published this specification (e.g., '3GPP')."""

    specification: str
    """Specification identifier (e.g., 'TS 24.008')."""

    url: str
    """Full HTTP URL to the specification."""


@dataclass
class TermResult:
    """A single term found in TEDDI with its definition and document references."""

    term: str
    """The term/abbreviation found."""

    description: str
    """Definition or description of the term."""

    documents: list[DocumentRef]
    """List of documents where this term is declared, grouped by technical body."""


@dataclass
class SearchRequest:
    """Request parameters for TEDDI search."""

    term: str
    """Term to search for."""

    search_in: SearchIn = SearchIn.BOTH
    """Scope: search in abbreviations, definitions, or both."""

    search_pattern: SearchPattern = SearchPattern.ALL_OCCURRENCES
    """Pattern: exact match, starts with, etc."""

    technical_bodies: list[TechnicalBody] | None = None
    """Filter by technical bodies. None or empty = all TBs."""


@dataclass
class SearchResponse:
    """Response from TEDDI search containing all matching terms."""

    query: SearchRequest
    """Original search request."""

    results: list[TermResult]
    """List of terms found matching the search criteria."""

    total_count: int
    """Total number of matching results."""
