"""
数据库模型 - 使用 SQLAlchemy ORM
SQLite 数据库，适合原型开发
"""

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Float, JSON, ForeignKey
from sqlalchemy.orm import sessionmaker, relationship, declarative_base
from datetime import datetime
import uuid

from config import SQLITE_URL

# 创建数据库引擎
engine = create_engine(SQLITE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def generate_id():
    """生成唯一ID"""
    return str(uuid.uuid4())[:8]

class Case(Base):
    """案件表"""
    __tablename__ = "cases"

    id = Column(String(20), primary_key=True, default=generate_id)
    name = Column(String(200), nullable=False)
    cause_type = Column(String(50), default="商标侵权")
    goal_type = Column(String(50))  # 要钱 / 要名
    client_org = Column(String(200))
    status = Column(String(50), default="draft")  # draft, evaluating, completed
    case_description = Column(Text)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # 关系
    parties = relationship("Party", back_populates="case", cascade="all, delete-orphan")
    evidence_files = relationship("EvidenceFile", back_populates="case", cascade="all, delete-orphan")
    evidence_facts = relationship("EvidenceFact", back_populates="case", cascade="all, delete-orphan")
    rule_hits = relationship("RuleHit", back_populates="case", cascade="all, delete-orphan")
    score_snapshots = relationship("ScoreSnapshot", back_populates="case", cascade="all, delete-orphan")
    moot_rounds = relationship("MootRound", back_populates="case", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="case", cascade="all, delete-orphan")

class Party(Base):
    """当事人表"""
    __tablename__ = "parties"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    role = Column(String(50))  # plaintiff, defendant
    name = Column(String(200))
    party_type = Column(String(50))  # individual, company
    external_profile_json = Column(JSON)

    case = relationship("Case", back_populates="parties")

class EvidenceFile(Base):
    """证据文件表"""
    __tablename__ = "evidence_files"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    file_name = Column(String(200))
    file_type = Column(String(50))
    storage_uri = Column(String(500))
    uploaded_by = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.now)

    case = relationship("Case", back_populates="evidence_files")

class EvidenceFact(Base):
    """证据事实表"""
    __tablename__ = "evidence_facts"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    chunk_id = Column(String(20))
    fact_text = Column(Text)
    fact_type = Column(String(50))
    time_point = Column(DateTime)
    subject_entity = Column(String(200))
    confidence = Column(Float)

    case = relationship("Case", back_populates="evidence_facts")

class LegalElement(Base):
    """法律要件表"""
    __tablename__ = "legal_elements"

    id = Column(String(20), primary_key=True, default=generate_id)
    cause_type = Column(String(50))
    element_code = Column(String(50))
    element_name = Column(String(200))
    element_description = Column(Text)
    required_level = Column(String(50))  # required, important, reference

class EvidenceMapping(Base):
    """证据映射表"""
    __tablename__ = "evidence_mappings"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    element_id = Column(String(20), ForeignKey("legal_elements.id"))
    fact_id = Column(String(20), ForeignKey("evidence_facts.id"))
    support_level = Column(String(50))  # strong, partial, weak, none
    proof_purpose = Column(String(200))

class Issue(Base):
    """争点表"""
    __tablename__ = "issues"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    issue_type = Column(String(50))
    issue_title = Column(String(200))
    issue_status = Column(String(50))  # pending, analyzing, concluded
    risk_level = Column(String(50))  # high, medium, low

class RuleHit(Base):
    """规则命中表"""
    __tablename__ = "rule_hits"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    rule_code = Column(String(50))
    severity = Column(String(50))  # block, warning, pass
    result = Column(String(50))
    reason = Column(Text)

    case = relationship("Case", back_populates="rule_hits")

class RetrievalRecord(Base):
    """检索记录表"""
    __tablename__ = "retrieval_records"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    query_text = Column(Text)
    query_type = Column(String(50))
    result_refs = Column(JSON)
    retrieval_score = Column(Float)

class ScoreSnapshot(Base):
    """评分快照表"""
    __tablename__ = "score_snapshots"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    legal_score = Column(Float)
    business_score = Column(Float)
    evidence_score = Column(Float)
    confidence_score = Column(Float)
    final_score = Column(Float)
    recommendation = Column(String(200))
    version = Column(Integer, default=1)

    case = relationship("Case", back_populates="score_snapshots")

class MootRound(Base):
    """模拟法庭轮次表"""
    __tablename__ = "moot_rounds"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    round_type = Column(String(50))
    speaker_role = Column(String(50))  # plaintiff, defendant, judge
    content = Column(Text)
    source_refs = Column(JSON)

    case = relationship("Case", back_populates="moot_rounds")

class Report(Base):
    """报告表"""
    __tablename__ = "reports"

    id = Column(String(20), primary_key=True, default=generate_id)
    case_id = Column(String(20), ForeignKey("cases.id"))
    report_type = Column(String(50))
    markdown_content = Column(Text)
    pdf_uri = Column(String(500))
    generated_at = Column(DateTime, default=datetime.now)

    case = relationship("Case", back_populates="reports")

def init_db():
    """初始化数据库"""
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库初始化完成")

def get_db():
    """获取数据库会话"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

if __name__ == "__main__":
    init_db()
