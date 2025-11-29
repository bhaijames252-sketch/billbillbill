from sqlalchemy import Column, String, JSON, DateTime, Boolean, Numeric
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class LatestPrice(Base):
    __tablename__ = "latest_prices"

    id = Column(String(36), primary_key=True)
    currency = Column(String(10), unique=True, nullable=False, index=True)
    compute = Column(JSON, nullable=False)
    disk = Column(JSON, nullable=False)
    floating_ip = Column(JSON, nullable=False)
    price_version = Column(String(50), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UserWallet(Base):
    __tablename__ = "user_wallets"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(50), unique=True, nullable=False, index=True)
    balance = Column(Numeric(precision=38, scale=18), nullable=False, default=0)
    currency = Column(String(10), nullable=False, default="USD")
    auto_recharge = Column(Boolean, nullable=False, default=False)
    allow_negative = Column(Boolean, nullable=False, default=True)
    last_deducted_at = Column(DateTime, nullable=True)
    mongo_archival_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
