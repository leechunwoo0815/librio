from backend.common.base_model import BaseModel
from sqlalchemy import BigInteger, Column, Integer, Text, DateTime


class BenefitTransferApplication(BaseModel):
    __tablename__ = "benefit_transfer_application"

    source_child_id = Column(BigInteger, nullable=False, comment="源孩子ID")
    target_child_id = Column(BigInteger, nullable=False, comment="目标孩子ID")
    user_id = Column(BigInteger, nullable=False, comment="申请人（家长）ID")
    status = Column(Integer, default=0, comment="状态: 0=PENDING 1=APPROVED 2=REJECTED")
    remark = Column(Text, comment="申请备注")
    reviewed_at = Column(DateTime, comment="审核时间")
    reviewer_id = Column(BigInteger, comment="审核人ID")
    review_remark = Column(Text, comment="审核备注")
