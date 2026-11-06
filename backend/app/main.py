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
    user_id: Mappeg7¶‰ËkºwµçA•‘}½±Õµ¸¡MÑÉ¥¹œ ÔÀÀ¤°¹Õ±±…‰±”õQÉÕ”¤(€€€¹ÕÑÉ¥Ñ¥½¹}‰…Í¥Ìè5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ĞÀ¤°‘•™…Õ±Ğô‰Á•É|ÄÀÁœˆ¤(€€€¹ÕÑÉ¥Ñ¥½¹}ÁÉ½Ù•¹…¹”è5…ÁÁ•‘m‘¥Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡)M=8°‘•™…Õ±Ğõ‘¥Ğ¤(€€€É•¥Á”è5…ÁÁ•‘m‘¥Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡)M=8°¹Õ±±…‰±”õQÉÕ”¤(€€€‘…Ñ…}¹½Ñ•Ìè5…ÁÁ•‘mÍÑÈğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÔÀÀ¤°¹Õ±±…‰±”õQÉÕ”¤(€€€¥µ…•}Á…Ñ è5…ÁÁ•‘mÍÑÈğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÔÀÀ¤°¹Õ±±…‰±”õQÉÕ”¤(€€€ÕÁ‘…Ñ•‘}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°‘•™…Õ±Ğõ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤°½¹ÕÁ‘…Ñ”õ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤¤(€€€­…°è5…ÁÁ•‘m™±½…Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡±½…Ğ°¹Õ±±…‰±”õQÉÕ”¤(€€€ÁÉ½Ñ•¥¸è5…ÁÁ•‘m™±½…Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡±½…Ğ°¹Õ±±…‰±”õQÉÕ”¤(€€€…É‰Ìè5…ÁÁ•‘m™±½…Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡±½…Ğ°¹Õ±±…‰±”õQÉÕ”¤(€€€™…Ğè5…ÁÁ•‘m™±½…Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡±½…Ğ°¹Õ±±…‰±”õQÉÕ”¤)±…ÍÌ½½‘M•ÉÙ¥¹œ¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰™½½‘}Í•ÉÙ¥¹Ìˆ(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€™½½‘}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰™½½‘Ì¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€±…‰•°è5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÄÀÀ¤¤(€€€É…µÌè5…ÁÁ•‘m™±½…Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡±½…Ğ¤(€€€Í½ÕÉ”è5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÈÀ¤°‘•™…Õ±Ğô‰ÕÍ•É}ÁÉ½Ù¥‘•ˆ¤)±…ÍÌ½½‘…Ù½É¥Ñ”¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰™½½‘}™…Ù½É¥Ñ•Ìˆ(€€€}}Ñ…‰±•}…ÉÍ}|€ô€¡U¹¥ÅÕ•½¹ÍÑÉ…¥¹Ğ ‰½İ¹•É}¥ˆ°€‰™½½‘}¥ˆ°¹…µ”ô‰ÕÅ}™½½‘}™…Ù½É¥Ñ•}½İ¹•É}™½½ˆ¤°¤(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€½İ¹•É}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰ÕÍ•ÉÌ¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€™½½‘}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰™½½‘Ì¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€É•…Ñ•‘}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°‘•™…Õ±Ğõ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤¤)±…ÍÌ½½‘I••¹Ğ¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰™½½‘}É••¹ÑÌˆ(€€€}}Ñ…‰±•}…ÉÍ}|€ô€¡U¹¥ÅÕ•½¹ÍÑÉ…¥¹Ğ ‰½İ¹•É}¥ˆ°€‰™½½‘}¥ˆ°¹…µ”ô‰ÕÅ}™½½‘}É••¹Ñ}½İ¹•É}™½½ˆ¤°¤(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€½İ¹•É}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰ÕÍ•ÉÌ¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€™½½‘}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰™½½‘Ì¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€Ù¥•İ•‘}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°‘•™…Õ±Ğõ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤°¥¹‘•àõQÉÕ”¤)±…ÍÌAÉ¥Ù…Ñ•¥±•±•…¹ÕÀ¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰ÁÉ¥Ù…Ñ•}™¥±•}±•…¹ÕÀˆ(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€ÁÉ¥Ù…Ñ•}Á…Ñ è5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÔÀÀ¤¤(€€€…ÑÑ•µÁÑÌè5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡‘•™…Õ±ĞôÀ¤(€€€É•…Ñ•‘}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°‘•™…Õ±Ğõ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤¤(€€€±…ÍÑ}…ÑÑ•µÁÑ}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ”ğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°¹Õ±±…‰±”õQÉÕ”¤)±…ÍÌM…¹M•ÍÍ¥½¸¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰Í…¹}Í•ÍÍ¥½¹Ìˆ(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€½İ¹•É}¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰ÕÍ•ÉÌ¹¥ˆ°½¹‘•±•Ñ”ô‰Mˆ¤°¥¹‘•àõQÉÕ”¤(€€€ÁÉ¥Ù…Ñ•}Á…Ñ è5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÔÀÀ¤¤(€€€…¹‘¥‘…Ñ•Ìè5…ÁÁ•‘m±¥ÍÑt€ôµ…ÁÁ•‘}½±Õµ¸¡)M=8°‘•™…Õ±Ğõ±¥ÍĞ¤(€€€ÍÑ…ÑÕÌè5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ÈÀ¤°‘•™…Õ±Ğô‰¹••‘Í}É•Ù¥•Üˆ¤(€€€µ•…±}¥è5…ÁÁ•‘m¥¹Ğğ9½¹•t€ôµ…ÁÁ•‘}½±Õµ¸¡½É•¥¹-•ä ‰µ•…±Ì¹¥ˆ°½¹‘•±•Ñ”ô‰MP9U10ˆ¤°¹Õ±±…‰±”õQÉÕ”¤(€€€É•…Ñ•‘}…Ğè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤°‘•™…Õ±Ğõ±…µ‰‘„è‘…Ñ•Ñ¥µ”¹¹½Ü¡Ñ¥µ•é½¹”¹ÕÑŒ¤¤)±…ÍÌI…Ñ•1¥µ¥Ñ	Õ­•Ğ¡	…Í”¤è(€€€}}Ñ…‰±•¹…µ•}|€ô€‰É…Ñ•}±¥µ¥Ñ}‰Õ­•ÑÌˆ(€€€}}Ñ…‰±•}…ÉÍ}|€ô€¡U¹¥ÅÕ•½¹ÍÑÉ…¥¹Ğ ‰Í½Á”ˆ°‰ÍÕ‰©•Ñ}‘¥•ÍĞˆ°‰İ¥¹‘½İ}ÍÑ…ÉĞˆ±¹…µ”ô‰ÕÅ}É…Ñ•}±¥µ¥Ñ}‰Õ­•Ğˆ¤°¤(€€€¥è5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡ÁÉ¥µ…Éå}­•äõQÉÕ”¤(€€€Í½Á”è5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ĞÀ¤¤(€€€ÍÕ‰©•Ñ}‘¥•ÍĞè5…ÁÁ•‘mÍÑÉt€ôµ…ÁÁ•‘}½±Õµ¸¡MÑÉ¥¹œ ØĞ¤¤(€€€İ¥¹‘½İ}ÍÑ…ÉĞè5…ÁÁ•‘m‘…Ñ•Ñ¥µ•t€ôµ…ÁÁ•‘}½±Õµ¸¡…Ñ•Q¥µ”¡Ñ¥µ•é½¹”õQÉÕ”¤¤(€€€½Õ¹Ğè5…ÁÁ•‘m¥¹Ñt€ôµ…ÁÁ•‘}½±Õµ¸¡‘•™…Õ±ĞôÀ¤)±…ÍÌ5•…°