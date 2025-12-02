from sqlalchemy import Boolean, Column, Integer, String, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String)
    last_name = Column(String, nullable=True)
    anon_link_uid = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Новые поля для монетизации
    balance = Column(Integer, default=0)  # Баланс в копейках
    premium_until = Column(DateTime, nullable=True)  # Дата окончания премиума
    available_reveals = Column(Integer, default=0)  # Доступные раскрытия

    received_messages = relationship("AnonMessage", foreign_keys="AnonMessage.receiver_id", back_populates="receiver")
    sent_messages = relationship("AnonMessage", foreign_keys="AnonMessage.sender_id", back_populates="sender")
    payments = relationship("Payment", back_populates="user")


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)  # Сумма в копейках
    payment_type = Column(String, nullable=False)  # reveal/day_sub/month_sub
    status = Column(String, default="pending")  # pending/waiting/completed/failed
    yookassa_payment_id = Column(String, nullable=True)  # ID платежа в ЮKassa
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    user = relationship("User", back_populates="payments")


class AnonMessage(Base):
    __tablename__ = "anon_messages"

    id = Column(Integer, primary_key=True, index=True)
    sender_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    receiver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    text = Column(Text, nullable=False)
    is_anonymous = Column(Boolean, default=True)
    is_revealed = Column(Boolean, default=False)
    is_reported = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow)

    # Для цепочки сообщений
    reply_to_message_id = Column(Integer, ForeignKey("anon_messages.id"), nullable=True)

    sender = relationship("User", foreign_keys=[sender_id], back_populates="sent_messages")
    receiver = relationship("User", foreign_keys=[receiver_id], back_populates="received_messages")
    reply_to = relationship("AnonMessage", remote_side=[id], backref="replies")


# Создаем индексы
Index('idx_messages_reply_to', AnonMessage.reply_to_message_id)
Index('idx_messages_receiver', AnonMessage.receiver_id)
Index('idx_messages_sender', AnonMessage.sender_id)
Index('idx_user_premium', User.premium_until)
Index('idx_payment_status', Payment.status)
Index('idx_payment_yookassa', Payment.yookassa_payment_id)
