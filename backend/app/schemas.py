from typing import List, Optional

from pydantic import BaseModel


class ColumnMapping(BaseModel):
    date: str
    description: str
    debit: Optional[str] = None
    credit: Optional[str] = None
    balance: Optional[str] = None


class Transaction(BaseModel):
    date: str
    description: str
    debit: Optional[float] = None
    credit: Optional[float] = None
    balance: Optional[float] = None

    # Transaction intelligence
    category: Optional[str] = None
    merchant: Optional[str] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    is_subscription: bool = False


class CategorizationResult(BaseModel):
    id: str
    category: str
    merchant: str = ""
    confidence: float = 0.5
    summary: str = ""


class CategorizationBatch(BaseModel):
    results: List[CategorizationResult]
