import asyncio
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import String, Text, JSON, DateTime, select, or_, and_, update
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# --- DATABASE SETUP ---
DATABASE_URL = "mysql+aiomysql://user:pass@localhost/kiraa_db"
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

class Base(DeclarativeBase): pass

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    conversationId: Mapped[str] = mapped_column(String(255))
    senderId: Mapped[str] = mapped_column(String(100))
    receiverId: Mapped[str] = mapped_column(String(100))
    message_type: Mapped[str] = mapped_column(String(20))
    content_text: Mapped[str] = mapped_column(Text)
    metadata_json: Mapped[dict] = mapped_column(JSON)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(20), default="delivered")

app = FastAPI()

# --- CORS MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[str(user_id)] = websocket

    def disconnect(self, user_id: str):
        self.active_connections.pop(str(user_id), None)

    async def send_to_user(self, message: dict, receiver_id: str):
        target_id = str(receiver_id)
        if target_id in self.active_connections:
            await self.active_connections[target_id].send_json(message)

manager = ConnectionManager()

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

# --- 1. FIXED HISTORY RETRIEVAL ---
@app.get("/messages/{u1}/{u2}")
async def get_history(u1: str, u2: str):
    user1 = str(u1).strip()
    user2 = str(u2).strip()
    
    async with AsyncSessionLocal() as session:
        stmt = select(Message).where(
            or_(
                and_(Message.senderId == user1, Message.receiverId == user2),
                and_(Message.senderId == user2, Message.receiverId == user1)
            )
        ).order_by(Message.timestamp.asc())
        print(Message.senderId)
        print(Message.receiverId)
        
        result = await session.execute(stmt)
        messages = result.scalars().all()
        
        # Maps keys to match exactly your frontend: m.senderId and m.text
        return [{"senderId": m.senderId, "text": m.content_text} for m in messages]

# --- 2. FIXED CONVERSATION INBOX ---
@app.get("/conversations/{user_id}")
async def get_conversations(user_id: str):
    target_uid = str(user_id).strip()
    
    async with AsyncSessionLocal() as session:
        stmt = select(Message).where(
            or_(Message.senderId == target_uid, Message.receiverId == target_uid)
        ).order_by(Message.timestamp.desc())
        
        result = await session.execute(stmt)
        all_msgs = result.scalars().all()
        
        processed = {}
        for msg in all_msgs:
            partner = msg.receiverId if msg.senderId == target_uid else msg.senderId
            if partner not in processed:
                # Count unread text blocks sent TO this user from this partner
                unread_count = sum(
                    1 for m in all_msgs 
                    if m.receiverId == target_uid and m.senderId == partner and m.status != "read"
                )

                processed[partner] = {
                    "authorId": partner,
                    "lastMessage": msg.content_text,
                    "time": msg.timestamp.strftime("%H:%M"),
                    "unread": unread_count
                }
        
        return list(processed.values())

# --- 3. HTTP MARK AS READ ---
@app.post("/messages/read/{user_id}/{partner_id}")
async def mark_as_read(user_id: str, partner_id: str):
    uid = str(user_id).strip()
    pid = str(partner_id).strip()
    
    async with AsyncSessionLocal() as session:
        stmt = (
            update(Message)
            .where(and_(Message.receiverId == uid, Message.senderId == pid))
            .values(status="read")
        )
        await session.execute(stmt)
        await session.commit()
        return {"status": "success"}

# --- DATABASE WRITER LAYER ---
async def save_message_to_db(data: dict):
    async with AsyncSessionLocal() as session:
        try:
            content = data.get('content', {})
            text_val = content.get('text', '')
            type_val = content.get('type', 'text')
            
            new_msg = Message(
                conversationId=str(data.get('conversationId', 'unknown')),
                senderId=str(data.get('senderId', 'unknown')),
                receiverId=str(data.get('receiverId', 'unknown')),
                message_type=type_val,
                content_text=text_val,
                metadata_json=content.get('metadata', {}),
                status="delivered"
            )
            session.add(new_msg)
            await session.commit()
        except Exception as e:
            await session.rollback()
            print(f"Database preservation error exception: {e}")

# --- 4. CORE WEBSOCKET ROUTER ---
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    current_uid = str(user_id).strip()
    await manager.connect(current_uid, websocket)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            # Action read_receipts payloads from active panels
            if data.get("type") == "read_receipt":
                partner_id = str(data.get("partnerId"))
                async with AsyncSessionLocal() as session:
                    stmt = update(Message).where(
                        and_(Message.receiverId == current_uid, Message.senderId == partner_id)
                    ).values(status="read")
                    await session.execute(stmt)
                    await session.commit()
                
                # Notify sender their message was read
                await manager.send_to_user({
                    "type": "messages_read",
                    "by_user": current_uid
                }, partner_id)

            # Route ordinary text message payloads
            else:
                await save_message_to_db(data)
                
                # Format to match your frontend live socket receiver template:
                # payload.senderId, payload.content.text
                formatted_payload = {
                    "conversationId": data.get("conversationId"),
                    "senderId": data.get("senderId"),
                    "receiverId": data.get("receiverId"),
                    "content": {
                        "type": data.get("content", {}).get("type", "text"),
                        "text": data.get("content", {}).get("text", "")
                    },
                    "timestamp": data.get("timestamp")
                }
                
                await manager.send_to_user(formatted_payload, data.get('receiverId'))

    except WebSocketDisconnect:
        manager.disconnect(current_uid)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8888)