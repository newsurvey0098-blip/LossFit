"""LossFit API foundation with persisted accounts, foods and meal snapshots."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import os, secrets, csv, io, json, ssl
import hashlib, hmac, smtplib
from uuid import uuid4
from email.message import EmailMessage
from typing import Generator, Literal
from pathlib import Path
import base64, difflib, re

import jwt
import httpx
from cryptography.fernet import Fernet
from PIL import Image, ImageOps, UnidentifiedImageError
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response, Query, UploadFile, File
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field, model_validator
from dotenv import load_dotenv
from sqlalchemy import create_engine, String, Text, Float, Boolean, DateTime, ForeignKey, JSON, select, func, delete, update, UniqueConstraint, or_, cast
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from .learning import LESSONS, LESSON_BY_SLUG, public_lesson
from .monitoring import RequestMonitoring
from .production import validate_production_environment
from .assistant_tools import generate as generate_assistant_reply
from .knowledge import content_hash, chunk_document, request_embeddings, retrieve as retrieve_knowledge

load_dotenv()
validate_production_environment(os.environ)
DB_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://lossfit@127.0.0.1:55432/lossfit")
JWT_SECRET = os.getenv("JWT_SECRET", "local-only-change-this-secret-before-deploying")
engine = create_engine(DB_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
hasher = PasswordHasher()

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    password_hash: Mapped[str] = mapped_column(String(255))
    goals: Mapped[dict] = mapped_column(JSON, default=lambda: {"calories": 2100, "protein": 140, "carbs": 220, "fat": 70})
    profile: Mapped[dict] = mapped_column(JSON, default=dict)
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id",ondelete="CASCADE"),index=True)
    refresh_token_hash: Mapped[str] = mapped_column(String(64),unique=True,index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime|None] = mapped_column(DateTime(timezone=True),nullable=True)
class GoogleAccount(Base):
    __tablename__ = "google_accounts"
    __table_args__ = (UniqueConstraint("provider_subject", name="uq_google_account_subject"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), unique=True)
    provider_subject: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class GoogleOAuthState(Base):
    __tablename__ = "google_oauth_states"
    state_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    nonce: Mapped[str] = mapped_column(String(128))
    code_verifier: Mapped[str] = mapped_column(String(128))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class Food(Base):
    __tablename__ = "foods"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    state: Mapped[str] = mapped_column(String(40), default="prepared")
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    aliases: Mapped[list] = mapped_column(JSON, default=list)
    verification: Mapped[str] = mapped_column(String(20), default="estimated")
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    nutrition_basis: Mapped[str] = mapped_column(String(40), default="per_100g")
    nutrition_provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    recipe: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    data_notes: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat: Mapped[float | None] = mapped_column(Float, nullable=True)
class FoodServing(Base):
    __tablename__ = "food_servings"
    id: Mapped[int] = mapped_column(primary_key=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(100))
    grams: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(20), default="user_provided")
class FoodFavorite(Base):
    __tablename__ = "food_favorites"
    __table_args__ = (UniqueConstraint("owner_id", "food_id", name="uq_food_favorite_owner_food"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class FoodRecent(Base):
    __tablename__ = "food_recents"
    __table_args__ = (UniqueConstraint("owner_id", "food_id", name="uq_food_recent_owner_food"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    food_id: Mapped[int] = mapped_column(ForeignKey("foods.id", ondelete="CASCADE"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
class PrivateFileCleanup(Base):
    __tablename__ = "private_file_cleanup"
    id: Mapped[int] = mapped_column(primary_key=True)
    private_path: Mapped[str] = mapped_column(String(500))
    attempts: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
class ScanSession(Base):
    __tablename__ = "scan_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    private_path: Mapped[str] = mapped_column(String(500))
    candidates: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="needs_review")
    meal_id: Mapped[int | None] = mapped_column(ForeignKey("meals.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class RateLimitBucket(Base):
    __tablename__ = "rate_limit_buckets"
    __table_args__ = (UniqueConstraint("scope","subject_digest","window_start",name="uq_rate_limit_bucket"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    scope: Mapped[str] = mapped_column(String(40))
    subject_digest: Mapped[str] = mapped_column(String(64))
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    count: Mapped[int] = mapped_column(default=0)
class Meal(Base):
    __tablename__ = "meals"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    meal_type: Mapped[str] = mapped_column(String(24))
    eaten_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    items: Mapped[list] = mapped_column(JSON)
    kcal: Mapped[float | None] = mapped_column(Float, nullable=True)
    protein: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbs: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat: Mapped[float | None] = mapped_column(Float, nullable=True)
class Water(Base):
    __tablename__ = "water_entries"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    ml: Mapped[int] = mapped_column()
    logged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class WeightRecord(Base):
    __tablename__ = "weight_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    weight_kg: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class PasswordReset(Base):
    __tablename__ = "password_resets"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AccountDeletionLedger(Base):
    __tablename__ = "account_deletion_ledger"
    id: Mapped[int] = mapped_column(primary_key=True)
    email_digest: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class Conversation(Base):
    __tablename__ = "assistant_conversations"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120), default="New conversation")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class ChatMessage(Base):
    __tablename__ = "assistant_messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))
    content: Mapped[str] = mapped_column(String(8000))
    citations: Mapped[list|None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AssistantTurn(Base):
    __tablename__ = "assistant_turns"
    __table_args__ = (UniqueConstraint("conversation_id", "idempotency_key", name="uq_assistant_turn_conversation_key"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    prompt: Mapped[str] = mapped_column(String(4000))
    answer: Mapped[str] = mapped_column(String(8000))
    citations: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class AssistantAction(Base):
    __tablename__ = "assistant_actions"
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_assistant_action_owner_key"),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("assistant_conversations.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(40))
    idempotency_key: Mapped[str] = mapped_column(String(64))
    arguments: Mapped[dict] = mapped_column(JSON)
    preview: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
class LessonProgress(Base):
    __tablename__ = "lesson_progress"
    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    lesson_slug: Mapped[str] = mapped_column(String(80))
    lesson_version: Mapped[int] = mapped_column()
    score: Mapped[int] = mapped_column()
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("owner_id", "lesson_slug", name="uq_lesson_progress_owner_slug"),)
class KnowledgeSource(Base):
    __tablename__ = "knowledge_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_key: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column()
    title: Mapped[str] = mapped_column(String(300))
    organization: Mapped[str] = mapped_column(String(180))
    url: Mapped[str] = mapped_column(String(1000))
    content_hash: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    __table_args__ = (UniqueConstraint("source_key", "version", name="uq_knowledge_source_version"),)
class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("knowledge_sources.id", ondelete="CASCADE"), index=True)
    chunk_index: Mapped[int] = mapped_column()
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list|None] = mapped_column(JSON, nullable=True)
    embedding_model: Mapped[str|None] = mapped_column(String(160), nullable=True)
    __table_args__ = (UniqueConstraint("source_id", "chunk_index", name="uq_knowledge_chunk_source_index"),)

class RegisterIn(BaseModel): name: str = Field(min_length=1,max_length=100); email: EmailStr; password: str = Field(min_length=10,max_length=128)
class LoginIn(BaseModel): email: EmailStr; password: str
class NutritionPer100(BaseModel):
    kcal:float|None=Field(default=None,ge=0,le=10000,allow_inf_nan=False);protein:float|None=Field(default=None,ge=0,le=1000,allow_inf_nan=False);carbs:float|None=Field(default=None,ge=0,le=1000,allow_inf_nan=False);fat:float|None=Field(default=None,ge=0,le=1000,allow_inf_nan=False)
class MealItemIn(BaseModel):
    food_id:int|None=None; snapshot_id:str|None=Field(default=None,max_length=64); name:str|None=Field(default=None,max_length=160);food:str|None=Field(default=None,max_length=160)
    state:str|None=Field(default=None,max_length=40);grams:float=Field(gt=0,le=10000,allow_inf_nan=False);portion_label:str|None=Field(default=None,max_length=100);per100:NutritionPer100=Field(default_factory=NutritionPer100)
class MealIn(BaseModel): name: str=Field(min_length=1,max_length=160,pattern=r".*\S.*"); meal_type: str=Field(pattern="^(breakfast|lunch|dinner|snack)$"); items: list[MealItemIn]=Field(max_length=50); eaten_at: datetime | None = None
class RecipeIngredientIn(BaseModel):
    food_id:int;grams:float=Field(gt=0,le=10000,allow_inf_nan=False);snapshot_id:str|None=Field(default=None,max_length=64)
class RecipeIn(BaseModel):
    name:str=Field(min_length=1,max_length=160,pattern=r".*\S.*")
    yield_grams:float=Field(gt=0,le=100000,allow_inf_nan=False)
    ingredients:list[RecipeIngredientIn]=Field(min_length=1,max_length=50)
class FoodIn(BaseModel):
    name: str=Field(min_length=1,max_length=160,pattern=r".*\S.*"); state: str=Field(default="prepared",pattern="^(raw|cooked|prepared|boiled|steamed|fried|grilled|roasted|baked|dried|frozen)$")
    kcal: float | None=Field(default=None,ge=0,le=10000,allow_inf_nan=False); protein: float | None=Field(default=None,ge=0,le=1000,allow_inf_nan=False); carbs: float | None=Field(default=None,ge=0,le=1000,allow_inf_nan=False); fat: float | None=Field(default=None,ge=0,le=1000,allow_inf_nan=False)
    brand: str|None=Field(default=None,max_length=120);category: str|None=Field(default=None,max_length=80); aliases:list[str]=Field(default_factory=list,max_length=24)
    serving_label:str|None=Field(default=None,max_length=100);serving_grams:float|None=Field(default=None,gt=0,le=10000,allow_inf_nan=False)
    @model_validator(mode="after")
    def validate_serving_pair(self):
        if bool(self.serving_label)!=bool(self.serving_grams):raise ValueError("Serving label and grams must be provided together")
        return self
class FoodServingIn(BaseModel): label:str=Field(min_length=1,max_length=100);grams:float=Field(gt=0,le=10000,allow_inf_nan=False)
class ScanCandidateIn(BaseModel): name:str=Field(min_length=1,max_length=160);grams:float=Field(default=100,ge=1,le=5000,allow_inf_nan=False)
class ScanConfirmItemIn(BaseModel): candidate_id:str|None=Field(default=None,max_length=64);food_id:int;grams:float=Field(gt=0,le=10000,allow_inf_nan=False);portion_label:str|None=Field(default=None,max_length=100)
class ScanConfirmIn(BaseModel): name:str=Field(min_length=1,max_length=160,pattern=r".*\S.*");meal_type:str=Field(pattern="^(breakfast|lunch|dinner|snack)$");items:list[ScanConfirmItemIn]=Field(max_length=50);removed_candidate_ids:list[str]=Field(default_factory=list,max_length=12)
class DeleteAccountIn(BaseModel): password:str=Field(min_length=1,max_length=128); confirmation:str
class GoogleLinkIn(BaseModel): password:str=Field(min_length=1,max_length=128)
class GoogleUnlinkIn(BaseModel): password:str=Field(min_length=1,max_length=128)
class ProfileIn(BaseModel): name:str|None=Field(default=None,min_length=1,max_length=100); goals:dict[str,float]|None=None
class PreferencesIn(BaseModel):
    diet:str=Field(min_length=1,max_length=40,pattern=r".*\S.*")
    allergies:list[str]=Field(default_factory=list,max_length=24)
    timezone:str=Field(min_length=1,max_length=64)
    units:str=Field(pattern="^(metric|imperial)$")
class ChatIn(BaseModel): conversation_id:int; message:str=Field(min_length=1,max_length=4000); idempotency_key:str=Field(min_length=16,max_length=64,pattern=r"^[A-Za-z0-9._:-]+$")
class AssistantActionPreviewIn(BaseModel):
    conversation_id:int
    action:Literal["log_water","log_meal"]
    water_ml:int|None=Field(default=None,ge=50,le=2000)
    meal:MealIn|None=None
    idempotency_key:str=Field(min_length=16,max_length=64,pattern=r"^[A-Za-z0-9._:-]+$")
    @model_validator(mode="after")
    def validate_arguments(self):
        if self.action=="log_water" and (self.water_ml is None or self.meal is not None):raise ValueError("Water actions need an amount and cannot include a meal")
        if self.action=="log_meal" and (self.meal is None or self.water_ml is not None or not self.meal.items):raise ValueError("Meal actions need at least one meal item and cannot include a water amount")
        if self.meal and self.meal.eaten_at and self.meal.eaten_at.tzinfo is None:raise ValueError("Meal time must include a timezone")
        return self
class QuizSubmissionIn(BaseModel): answers:list[int]=Field(min_length=1,max_length=10)
class OnboardingIn(BaseModel):
    age:int=Field(ge=18,le=100); sex:str=Field(pattern="^(female|male|other)$"); height_cm:float=Field(ge=120,le=230); weight_kg:float=Field(ge=35,le=300)
    goal:str=Field(pattern="^(weight_loss|maintenance|muscle_gain|balanced)$"); activity:str=Field(pattern="^(sedentary|light|moderate|active)$")
    diet:str=Field(default="no_restrictions",max_length=40); allergies:list[str]=Field(default_factory=list,max_length=24)
    timezone:str=Field(default="Asia/Kolkata",max_length=64); units:str=Field(default="metric",pattern="^(metric|imperial)$")
class WeightIn(BaseModel): weight_kg:float=Field(gt=20,le=350); recorded_at:datetime|None=None
class ForgotPasswordIn(BaseModel): email:EmailStr
class ResetPasswordIn(BaseModel): token:str=Field(min_length=32,max_length=256); password:str=Field(min_length=10,max_length=128)

def clean_aliases(name:str,values:list[str])->list[str]:
    seen={name.strip().casefold()};out=[]
    for value in values:
        alias=" ".join(value.split())
        if alias and len(alias)<=160 and alias.casefold() not in seen:
            seen.add(alias.casefold());out.append(alias)
    return out[:24]

def enforce_rate_limit(s:Session,scope:str,subject:str,limit:int,window_seconds:int):
    now=datetime.now(timezone.utc);window_start=datetime.fromtimestamp(int(now.timestamp())//window_seconds*window_seconds,timezone.utc)
    digest=hmac.new(JWT_SECRET.encode(),(scope+":"+subject).encode(),hashlib.sha256).hexdigest()
    statement=postgres_insert(RateLimitBucket).values(scope=scope,subject_digest=digest,window_start=window_start,count=1).on_conflict_do_update(
        constraint="uq_rate_limit_bucket",set_={"count":RateLimitBucket.count+1}
    ).returning(RateLimitBucket.count)
    count=s.scalar(statement);s.commit()
    if count%100==0:
        s.execute(delete(RateLimitBucket).where(RateLimitBucket.window_start<now-timedelta(days=2)));s.commit()
    if count>limit:
        remaining=window_seconds-int(now.timestamp())%window_seconds
        raise HTTPException(429,"Too many requests. Please wait before trying again.",headers={"Retry-After":str(remaining)})

def request_ip(request:Request)->str:
    return request.client.host if request.client else "unknown"

def google_oauth_configured()->bool:
    return all(os.getenv(name) for name in ("GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REDIRECT_URI"))

def oauth_secret_box()->Fernet:
    key=base64.urlsafe_b64encode(hashlib.sha256(("lossfit-google-oauth:"+JWT_SECRET).encode()).digest())
    return Fernet(key)

def verify_google_id_token(raw_token:str, audience:str)->dict:
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token
    return id_token.verify_oauth2_token(raw_token, GoogleRequest(), audience)

app=FastAPI(title="LossFit API",version="0.1.0")
if os.getenv("ENVIRONMENT")=="production" and (len(JWT_SECRET)<32 or JWT_SECRET=="local-only-change-this-secret-before-deploying"):
    raise RuntimeError("Production requires a unique JWT_SECRET of at least 32 characters")
if os.getenv("ENVIRONMENT")=="production" and len(os.getenv("DELETION_LEDGER_SECRET",""))<32:
    raise RuntimeError("Production requires a stable DELETION_LEDGER_SECRET of at least 32 characters")
if os.getenv("ENVIRONMENT")=="production" and google_oauth_configured() and not os.environ["GOOGLE_REDIRECT_URI"].lower().startswith("https://"):
    raise RuntimeError("Production Google OAuth requires an HTTPS redirect URI")
app.add_middleware(CORSMiddleware,allow_origins=os.getenv("CORS_ORIGINS","http://localhost:5173,http://127.0.0.1:5173").split(","),allow_credentials=True,allow_methods=["GET","POST","PUT","PATCH","DELETE"],allow_headers=["Authorization","Content-Type","X-CSRF-Token"])
app.add_middleware(RequestMonitoring)
@app.middleware("http")
async def csrf_protection(request:Reques…45727 tokens truncated…f(active)setPhotoUrl(objectUrl);else URL.revokeObjectURL(objectUrl)}).catch(e=>active&&setError(e.message));else setPhotoUrl('');return()=>{active=false;if(objectUrl)URL.revokeObjectURL(objectUrl)}},[food?.id,food?.image_url]);
 async function removePhoto(){if(!food)return;try{await api(`/foods/${food.id}/image`,{method:'DELETE'});setFood({...food,image_url:null});setPhotoUrl('')}catch(e:any){setError(e.message)}}
 async function toggleFavorite(){if(!food)return;setError('');try{await api(`/foods/${food.id}/favorite`,{method:food.is_favorite?'DELETE':'PUT'});setFood({...food,is_favorite:!food.is_favorite})}catch(e:any){setError(e.message)}}
 async function add(){if(!food)return;setError('');try{await api('/meals',{method:'POST',body:JSON.stringify({name:food.name,meal_type:mealType,items:[{food_id:food.id,name:food.name,grams,portion_label:serving||`${grams} g`,per100:{kcal:food.kcal,protein:food.protein,carbs:food.carbs,fat:food.fat}}]})});setSaved(true)}catch(e:any){setError(e.message)}}
 if(error&&!food)return <section className="card simple"><h1>Food unavailable</h1><p className="error" role="alert">{error}</p><Link className="button primary" to="/foods">Back to foods</Link></section>;if(!food)return <p role="status">Loading food…</p>;
 const value=(n:number|null,unit='g')=>n===null?'Not available':`${(n*grams/100).toFixed(1)}${unit}`;
 return <><p className="eyebrow">{food.verification.replace('_',' ').toUpperCase()} · {food.state.toUpperCase()}</p><div className="sectionhead"><h1>{food.name}</h1><button type="button" className="icon favorite-toggle" aria-label={`${food.is_favorite?'Remove from':'Add to'} favorites`} aria-pressed={Boolean(food.is_favorite)} onClick={toggleFavorite}><Heart size={19} fill={food.is_favorite?'currentColor':'none'}/></button></div>{photoUrl&&<figure className="food-photo-display"><img src={photoUrl} alt={`${food.name} food photo`}/>{food.is_custom&&<button className="button danger" onClick={removePhoto}>Remove photo</button>}</figure>}<p className="muted">Nutrition shown per 100 g, adjusted for your portion. {food.source_url?<a href={food.source_url} target="_blank" rel="noreferrer">{food.source??'Nutrition source'}</a>:food.source??'Source not recorded'}{food.source_record_id?` · record ${food.source_record_id}`:''}</p>{food.data_notes&&<p className="integration-note" role="status">Data note: {food.data_notes}</p>}<>{food.recipe&&<section className="card manualform"><h2>Recipe ingredients</h2><p>Finished yield: {food.recipe.yield_grams} g</p><ul>{food.recipe.ingredients.map((i,n)=><li key={n}>{i.name} · {i.state} · {i.grams} g</li>)}</ul></section>}</><div className="nutrient-provenance" aria-label="Nutrition value sources">{[['kcal','Calories'],['protein','Protein'],['carbs','Carbohydrates'],['fat','Fat']].map(([key,label])=><span key={key}>{label}: {food.nutrition_provenance?.[key]?.status??(food[key as keyof Food]===null?'unavailable':'source not recorded')}</span>)}</div><section className="card manualform">{food.servings?.length?<label>Choose a serving<select value={serving} onChange={e=>{setServing(e.target.value);const v=food.servings?.find(x=>x.label===e.target.value);if(v)setGrams(v.grams)}}>{food.servings.map(v=><option key={v.id} value={v.label}>{v.label} ({v.grams} g)</option>)}<option value="">Custom grams</option></select></label>:null}<label>Portion size (grams)<input type="number" min="1" max="3000" value={grams} onChange={e=>{setServing('');setGrams(Math.max(1,Number(e.target.value)||1))}}/></label><div className="nutrients large"><span><b>{value(food.kcal,'')}</b> kcal</span><span><b>{value(food.protein)}</b> protein</span><span><b>{value(food.carbs)}</b> carbs</span><span><b>{value(food.fat)}</b> fat</span></div><label>Meal<select value={mealType} onChange={e=>setMealType(e.target.value)}>{['breakfast','lunch','dinner','snack'].map(v=><option key={v}>{v}</option>)}</select></label>{error&&<p role="alert" className="error">{error}</p>}{saved?<p className="success" role="status">Added to your meal log.</p>:<button className="button primary" onClick={add}>Add to meal</button>}{food.is_custom&&<Link className="button" to={food.recipe?`/recipes/${food.id}/edit`:`/foods/${food.id}/edit`}>{food.recipe?'Edit recipe':'Edit custom food'}</Link>}<Link className="textlink" to="/foods">Back to catalogue</Link></section></>
}

export function EditFoodPage(){
 const {foodId}=useParams();const nav=useNavigate();const [food,setFood]=React.useState<Food|null>(null);const [error,setError]=React.useState('');const [saved,setSaved]=React.useState(false);const [busy,setBusy]=React.useState(false);
 React.useEffect(()=>{api<Food>(`/foods/${foodId}`).then(v=>{if(!v.is_custom)throw new Error('Only your personal foods can be edited');setFood(v)}).catch(e=>setError(e.message))},[foodId]);
 async function save(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!food)return;const fd=new FormData(e.currentTarget);const num=(k:string)=>fd.get(k)===''?null:Number(fd.get(k));setBusy(true);setError('');try{const updated=await api<Food>(`/foods/${food.id}`,{method:'PUT',body:JSON.stringify({name:fd.get('name'),brand:fd.get('brand')||null,category:fd.get('category')||null,aliases:String(fd.get('aliases')||'').split(',').map(x=>x.trim()).filter(Boolean),state:fd.get('state'),kcal:num('kcal'),protein:num('protein'),carbs:num('carbs'),fat:num('fat'),serving_label:fd.get('serving_label')||null,serving_grams:fd.get('serving_grams')===''?null:Number(fd.get('serving_grams'))})});setFood(updated);setSaved(true)}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 async function addServing(e:React.FormEvent<HTMLFormElement>){e.preventDefault();if(!food)return;const fd=new FormData(e.currentTarget);setBusy(true);setError('');try{await api(`/foods/${food.id}/servings`,{method:'POST',body:JSON.stringify({label:fd.get('label'),grams:Number(fd.get('grams'))})});setFood(await api<Food>(`/foods/${food.id}`));e.currentTarget.reset()}catch(e:any){setError(e.message)}finally{setBusy(false)}}
 async function deleteServing(serving:Serving){if(!food||!window.confirm(`Remove the serving “${serving.label}”?`))return;try{await api(`/foods/${food.id}/servings/${serving.id}`,{method:'DELETE'});setFood(await api<Food>(`/foods/${food.id}`))}catch(e:any){setError(e.message)}}
 async function removeFood(){if(!food||!window.confirm('Delete this custom food? Existing logged meals keep their nutrition snapshots.'))return;setBusy(true);try{await api(`/foods/${food.id}`,{method:'DELETE'});nav('/foods')}catch(e:any){setError(e.message);setBusy(false)}}
 if(error&&!food)return <section className="card simple"><h1>Food unavailable</h1><p className="error" role="alert">{error}</p><Link to="/foods" className="button">Back to foods</Link></section>;if(!food)return <p role="status">Loading food…</p>;
 return <><p className="eyebrow">PERSONAL FOOD</p><h1>Edit food</h1><p className="muted">Updates apply to future meal entries. Previously logged meals retain the original nutrition snapshot.</p><form className="card manualform" onSubmit={save}><label>Name<input name="name" required maxLength={160} defaultValue={food.name}/></label><div className="formgrid"><label>Brand<input name="brand" maxLength={120} defaultValue={food.brand??''}/></label><label>Category<input name="category" maxLength={80} defaultValue={food.category??''}/></label></div><label>Search aliases<input name="aliases" maxLength={500} defaultValue={(food.aliases??[]).join(', ')}/></label><label>Preparation state<select name="state" defaultValue={food.state}>{['prepared','raw','cooked','boiled','steamed','fried','grilled','roasted','baked','dried','frozen'].map(x=><option key={x}>{x}</option>)}</select></label><div className="formgrid">{[['kcal','Calories (kcal)'],['protein','Protein (g)'],['carbs','Carbohydrates (g)'],['fat','Fat (g)']].map(([key,label])=><label key={key}>{label}<input name={key} type="number" min="0" step="0.1" placeholder="Unknown" defaultValue={String(food[key as keyof Food]??'')}/></label>)}</div><div className="formgrid"><label>Add serving label<input name="serving_label" maxLength={100} placeholder="e.g. 1 bowl"/></label><label>Serving weight (g)<input name="serving_grams" type="number" min="0.1" step="0.1"/></label></div>{error&&<p role="alert" className="error">{error}</p>}{saved&&<p role="status" className="success">Food details saved.</p>}<div className="actions"><button className="button primary" disabled={busy}>{busy?'Saving…':'Save changes'}</button><button type="button" className="button danger" disabled={busy} onClick={removeFood}>Delete food</button><Link className="button" to={`/foods/${food.id}`}>View details</Link></div></form><section className="card manualform"><h2>Serving shortcuts</h2><ul className="serving-list">{food.servings?.map(x=><li key={x.id}><span>{x.label} · {x.grams} g <small>({x.source.replace('_',' ')})</small></span>{x.source!=='standard'&&<button className="button danger" onClick={()=>deleteServing(x)}>Remove</button>}</li>)}</ul><form className="formgrid" onSubmit={addServing}><label>Serving label<input name="label" required maxLength={100} placeholder="1 medium piece"/></label><label>Serving weight (g)<input name="grams" type="number" required min="0.1" max="10000" step="0.1"/></label><button className="button" disabled={busy}>Add serving</button></form></section></>
}
