from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, String, Integer, JSON, DateTime, Text
from datetime import datetime
import os
from .schemas import TeachingStyle, EmotionalState, MasteryLevel
import dotenv

dotenv.load_dotenv()

Base = declarative_base()

class UserProfile(Base):
    __tablename__ = "user_profiles"
    
    user_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    grade_level = Column(String, nullable=False)
    learning_style_summary = Column(Text, nullable=False)
    emotional_state_summary = Column(Text, nullable=False)
    mastery_level_summary = Column(Text, nullable=False)
    preferred_teaching_style = Column(String, default=TeachingStyle.DIRECT)
    current_emotional_state = Column(String, default=EmotionalState.FOCUSED)
    current_mastery_level = Column(Integer, default=MasteryLevel.LEVEL_1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Enhanced sample user data with educational context
SAMPLE_USERS = {
    "student123": {
        "user_id": "student123",
        "name": "Charlie",
        "grade_level": "8",
        "learning_style_summary": "Kinesthetic learner, learns best through practice and repetition",
        "emotional_state_summary": "Focused and motivated to improve",
        "mastery_level_summary": "Level 6: Good understanding, ready for application",
        "preferred_teaching_style": TeachingStyle.DIRECT,
        "current_emotional_state": EmotionalState.FOCUSED,
        "current_mastery_level": MasteryLevel.LEVEL_6
    },
    "student456": {
        "user_id": "student456", 
        "name": "Alice",
        "grade_level": "10",
        "learning_style_summary": "Visual learner, prefers diagrams and structured notes",
        "emotional_state_summary": "Anxious about new concepts", 
        "mastery_level_summary": "Level 3: Building foundational knowledge",
        "preferred_teaching_style": TeachingStyle.VISUAL,
        "current_emotional_state": EmotionalState.ANXIOUS,
        "current_mastery_level": MasteryLevel.LEVEL_3
    },
    "student789": {
        "user_id": "student789",
        "name": "Bob", 
        "grade_level": "7",
        "learning_style_summary": "Auditory learner, prefers simple terms and step-by-step explanations",
        "emotional_state_summary": "Confused about current topic",
        "mastery_level_summary": "Level 4: Building foundational knowledge", 
        "preferred_teaching_style": TeachingStyle.SOCRATIC,
        "current_emotional_state": EmotionalState.CONFUSED,
        "current_mastery_level": MasteryLevel.LEVEL_4
    }
}

class Database:
    def __init__(self):
        self.engine = create_async_engine(
            os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./test.db"), echo=False
        )
        self.async_session = sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )
    
    async def get_user_profile(self, user_id: str) -> dict:
        # For now, return from sample data. In production, query database
        return SAMPLE_USERS.get(user_id, SAMPLE_USERS["student123"])