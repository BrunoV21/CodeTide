try:
    from sqlalchemy.orm import declarative_base, relationship, mapped_column
    from sqlalchemy import String, Text, ForeignKey, Boolean, Integer
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy.types import TypeDecorator
except ImportError as e:
    raise ImportError(
        "This module requires 'sqlalchemy' and 'ulid-py'. "
        "Install them with: pip install codetide[agents-ui]"
    ) from e

from datetime import datetime
from sqlalchemy import Select
from ulid import ulid
import asyncio
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
async def init_db(path: str):
    from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession
    engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
           # Test ORM behavior
    async_session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        # Get a user using ORM
        users = await session.execute(Select(User).limit(1))
        user = users.scalar_one_or_none()
        
        if user:
            print("\n=== ORM TEST ===")
            print(f"user.user_metadata type: {type(user.user_metadata)}")
            print(f"user.user_metadata value: {user.user_metadata}")
            
        # Get a thread using ORM  
        threads = await session.execute(Select(Thread).limit(1))
        thread = threads.scalar_one_or_none()
        
        if thread:
            print(f"thread.user_metadata type: {type(thread.user_metadata)}")
            print(f"thread.user_metadata value: {thread.user_metadata}")


if __name__ == "__main__":
    asyncio.run(init_db("database.db"))
