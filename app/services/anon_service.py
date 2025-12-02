import secrets
import string
from sqlalchemy.orm import Session
from app.models import User, AnonMessage


class AnonService:
    def generate_link_uid(self, length=10):
        """Генерация уникального ID для ссылки"""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def create_or_update_anon_link(self, db: Session, user_id: int):
        """Создание или обновление анонимной ссылки пользователя"""
        try:
            user = db.query(User).filter(User.id == user_id).first()
            if not user:
                return None

            # Всегда генерируем новую ссылку
            user.anon_link_uid = self.generate_link_uid()
            db.commit()
            db.refresh(user)

            return user.anon_link_uid
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка создания ссылки: {e}")
            return None

    def get_user_by_link_uid(self, db: Session, link_uid: str):
        """Получить пользователя по UID ссылки"""
        try:
            return db.query(User).filter(User.anon_link_uid == link_uid).first()
        except Exception as e:
            print(f"❌ Ошибка поиска пользователя: {e}")
            return None

    def get_or_create_user(self, db: Session, telegram_id: int, username: str = None, first_name: str = None,
                           last_name: str = None):
        """Получить или создать пользователя"""
        try:
            user = db.query(User).filter(User.telegram_id == telegram_id).first()
            if not user:
                user = User(
                    telegram_id=telegram_id,
                    username=username,
                    first_name=first_name,
                    last_name=last_name
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            return user
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка создания пользователя: {e}")
            return None

    def add_anon_message(self, db: Session, receiver_link_uid: str, text: str, sender_id: int = None,
                         reply_to_message_id: int = None):
        """Добавить анонимное сообщение"""
        try:
            print(f"🔍 Поиск получателя с UID ссылки: {receiver_link_uid}")

            receiver = self.get_user_by_link_uid(db, receiver_link_uid)
            if not receiver:
                print(f"❌ Получатель с UID {receiver_link_uid} не найден")
                return None

            print(f"✅ Получатель найден: TG ID={receiver.telegram_id}, Имя={receiver.first_name}")

            message = AnonMessage(
                sender_id=sender_id,
                receiver_id=receiver.id,
                text=text,
                is_anonymous=sender_id is None,
                reply_to_message_id=reply_to_message_id
            )

            db.add(message)
            db.commit()
            db.refresh(message)

            print(f"✅ Сообщение сохранено: ID={message.id}")

            return message, receiver.telegram_id
        except Exception as e:
            db.rollback()
            print(f"❌ Ошибка сохранения сообщения: {e}")
            return None

    def get_user_received_messages(self, db: Session, user_id: int):
        """Получить все полученные сообщения пользователя"""
        try:
            return db.query(AnonMessage).filter(AnonMessage.receiver_id == user_id).order_by(
                AnonMessage.timestamp.desc()).all()
        except Exception as e:
            print(f"❌ Ошибка получения сообщений: {e}")
            return []

    def get_message_by_id(self, db: Session, message_id: int):
        """Получить сообщение по ID"""
        try:
            return db.query(AnonMessage).filter(AnonMessage.id == message_id).first()
        except Exception as e:
            print(f"❌ Ошибка поиска сообщения: {e}")
            return None

    def get_conversation_thread(self, db: Session, original_message_id: int):
        """Получить всю цепочку сообщений начиная с оригинального"""
        try:
            messages = []
            current_message = self.get_message_by_id(db, original_message_id)

            while current_message:
                messages.append(current_message)
                # Идем вверх по цепочке ответов
                if current_message.reply_to_message_id:
                    current_message = self.get_message_by_id(db, current_message.reply_to_message_id)
                else:
                    break

            return list(reversed(messages))  # Возвращаем в хронологическом порядке
        except Exception as e:
            print(f"❌ Ошибка получения цепочки: {e}")
            return []

    def get_original_sender_link(self, db: Session, message_id: int):
        """Получить ссылку оригинального отправителя для ответа"""
        try:
            message = self.get_message_by_id(db, message_id)
            if not message:
                return None

            # Если это ответ на другое сообщение, идем к оригинальному сообщению
            if message.reply_to_message_id:
                original_message = self.get_message_by_id(db, message.reply_to_message_id)
                if original_message and original_message.sender and original_message.sender.anon_link_uid:
                    return original_message.sender.anon_link_uid

            # Если это первое сообщение в цепочке
            if message.sender and message.sender.anon_link_uid:
                return message.sender.anon_link_uid

            return None
        except Exception as e:
            print(f"❌ Ошибка получения ссылки отправителя: {e}")
            return None

    def get_user_stats(self, db: Session, user_id: int):
        """Статистика пользователя"""
        try:
            total_messages = db.query(AnonMessage).filter(AnonMessage.receiver_id == user_id).count()
            has_link = db.query(User).filter(User.id == user_id, User.anon_link_uid.isnot(None)).first() is not None

            return {
                'total_messages': total_messages,
                'has_link': has_link
            }
        except Exception as e:
            print(f"❌ Ошибка получения статистики: {e}")
            return {'total_messages': 0, 'has_link': False}


anon_service = AnonService()
