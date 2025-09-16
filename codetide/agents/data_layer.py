try:
    from sqlalchemy.orm import declarative_base, relationship, mapped_column
    from sqlalchemy import String, Text, ForeignKey, Boolean, Integer
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.types import TypeDecorator
    from sqlalchemy.exc import OperationalError
except ImportError as e:
    raise ImportError(
        "This module requires 'sqlalchemy' and 'ulid-py'. "
        "Install them with: pip install codetide[agents-ui]"
    ) from e   

import asyncio
from datetime import datetime
from ulid import ulid
import json

# SQLite-compatible JSON and UUID types
class GUID(TypeDecorator):
    impl = String

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value)

    def process_result_value(self, value, dialect):
        return value
class JSONEncodedDict(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value is not None else None

class JSONEncodedList(TypeDecorator):
    impl = Text

    def process_bind_param(self, value, dialect):
        return json.dumps(value) if value is not None else None

    def process_result_value(self, value, dialect):
        return json.loads(value) if value is not None else None

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = mapped_column(GUID, primary_key=True, default=ulid)
    identifier = mapped_column(Text, unique=True, nullable=False)
    user_metadata = mapped_column("metadata", JSONEncodedDict, nullable=False)
    createdAt = mapped_column(Text, default=lambda: datetime.utcnow().isoformat())

class Thread(Base):
    __tablename__ = "threads"
    id = mapped_column(GUID, primary_key=True, default=ulid)
    createdAt = mapped_column(Text, default=lambda: datetime.utcnow().isoformat())
    name = mapped_column(Text)
    userId = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"))
    userIdentifier = mapped_column(Text)
    tags = mapped_column(JSONEncodedList)
    user_metadata = mapped_column("metadata", JSONEncodedDict)

    user = relationship("User", backref="threads")

class Step(Base):
    __tablename__ = "steps"
    id = mapped_column(GUID, primary_key=True, default=ulid)
    name = mapped_column(Text, nullable=False)
    type = mapped_column(Text, nullable=False)
    threadId = mapped_column(GUID, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    parentId = mapped_column(GUID)
    streaming = mapped_column(Boolean, nullable=False)
    waitForAnswer = mapped_column(Boolean)
    isError = mapped_column(Boolean)
    user_metadata = mapped_column("metadata", JSONEncodedDict)
    tags = mapped_column(JSONEncodedList)
    input = mapped_column(Text)
    output = mapped_column(Text)
    createdAt = mapped_column(Text, default=lambda: datetime.utcnow().isoformat())
    command = mapped_column(Text)
    start = mapped_column(Text)
    end = mapped_column(Text)
    generation = mapped_column(JSONEncodedDict)
    showInput = mapped_column(Text)
    language = mapped_column(Text)
    indent = mapped_column(Integer)
    defaultOpen = mapped_column(Boolean, default=False)

class Element(Base):
    __tablename__ = "elements"
    id = mapped_column(GUID, primary_key=True, default=ulid)
    threadId = mapped_column(GUID, ForeignKey("threads.id", ondelete="CASCADE"))
    type = mapped_column(Text)
    url = mapped_column(Text)
    chainlitKey = mapped_column(Text)
    name = mapped_column(Text, nullable=False)
    display = mapped_column(Text)
    objectKey = mapped_column(Text)
    size = mapped_column(Text)
    page = mapped_column(Integer)
    language = mapped_column(Text)
    forId = mapped_column(GUID)
    mime = mapped_column(Text)
    props = mapped_column(JSONEncodedDict)

class Feedback(Base):
    __tablename__ = "feedbacks"
    id = mapped_column(GUID, primary_key=True, default=ulid)
    forId = mapped_column(GUID, nullable=False)
    threadId = mapped_column(GUID, ForeignKey("threads.id", ondelete="CASCADE"), nullable=False)
    value = mapped_column(Integer, nullable=False)
    comment = mapped_column(Text)

# class AsyncMessageDB:
#     def __init__(self, db_path: str):
#         self.db_url = f"sqlite+aiosqlite:///{db_path}"
#         self.engine = create_async_engine(self.db_url, echo=False)
#         self.async_session = async_sessionmaker(bind=self.engine, class_=AsyncSession, expire_on_commit=False)

#     async def init_db(self):
#         async with self.engine.begin() as conn:
#             await conn.run_sync(Base.user_metadata.create_all)

#     async def create_chat(self, name: str) -> Chat:
#         async with self.async_session() as session:
#             chat = Chat(name=name)
#             session.add(chat)
#             await session.commit()
#             await session.refresh(chat)
#             return chat

#     async def add_message(self, chat_id: str, role: str, content: str) -> Message:
#         async with self.async_session() as session:
#             message = Message(chat_id=chat_id, role=role, content=content)
#             session.add(message)
#             await session.commit()
#             await session.refresh(message)
#             return message

#     async def get_messages_for_chat(self, chat_id: str) -> List[Message]:
#         async with self.async_session() as session:
#             result = await session.execute(
#                 select(Message).where(Message.chat_id == chat_id).order_by(Message.timestamp)
#             )
#             return result.scalars().all()

#     async def list_chats(self) -> List[Chat]:
#         async with self.async_session() as session:
#             result = await session.execute(select(Chat).order_by(Chat.name))
#             return result.scalars().all()
        
# async def main():
#     db = AsyncMessageDB(str(Path(os.path.abspath(__file__)).parent / "my_messages.db"))
#     await db.init_db()

#     chat = await db.create_chat("My First Chat")
#     await db.add_message(chat.id, "user", "Hello Assistant!")
#     await db.add_message(chat.id, "assistant", "Hello, how can I help you?")

#     print(f"Messages for chat '{chat.name}':")
#     messages = await db.get_messages_for_chat(chat.id)
#     for msg in messages:
#         print(f"[{msg.timestamp}] {msg.role.upper()}: {msg.content}")

#     print("\nAll chats:")
#     chats = await db.list_chats()
#     for c in chats:
#         print(f"{c.id} — {c.name}")

async def init_db(conn_str: str, max_retries: int = 5, retry_delay: int = 2):
    """
    Initialize database with retry logic for connection issues.
    """
    engine = create_async_engine(conn_str)
    
    for attempt in range(max_retries):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            print("Database initialized successfully!")
            return
        except OperationalError as e:
            if attempt == max_retries - 1:
                print(f"Failed to initialize database after {max_retries} attempts: {e}")
                raise
            else:
                print(f"Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
        except Exception as e:
            print(f"Unexpected error initializing database: {e}")
        raise
