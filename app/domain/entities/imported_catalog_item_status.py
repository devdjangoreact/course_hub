from enum import StrEnum


class ImportedCatalogItemStatus(StrEnum):
    DRAFT = "draft"
    MATCHED = "matched"
    APPROVED = "approved"
    REJECTED = "rejected"
