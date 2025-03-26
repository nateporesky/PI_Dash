from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import Column, Integer, String, Boolean, create_engine
from sqlalchemy import DateTime, func, Float
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from pydantic import BaseModel
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext
import logging
from fastapi.middleware.cors import CORSMiddleware


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# JWT Configuration
SECRET_KEY = "SECRET_KEYajnkjnknsc"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1800  # 30 hours

app = FastAPI()

# Allowed frontend origins (Modify this based on your frontend URL)
origins = [
    "http://localhost:3000",  # React, Vue, or Angular running locally
    "http://127.0.0.1:3000",
    "https://yourfrontenddomain.com",  # Production frontend URL
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin (for development only)
    allow_credentials=True,
    allow_methods=["*"], # Allow all HTTP methods (GET, POST, PUT, DELETE)
    allow_headers=["*"], # Allow all headers
)

# Password Hashing Configuration
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth_2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# SQLAlchemy Setup (In-Memory Database)
#DATABASE_URL = "sqlite:///:memory:"
DATABASE_URL = "sqlite:///./test.db"  # Persistent database file
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class UserDB(Base):
    """SQLAlchemy Model for Users"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, nullable=False)
    hashed_password = Column(String, nullable=False)
    disabled = Column(Boolean, default=False)
    last_login = Column(String, default=datetime.now(timezone.utc).isoformat())
    is_admin = Column(Boolean, default=False)


class QuotaDB(Base):
    """SQLAlchemy Model for Quotas"""
    __tablename__ = "quotas"

    quota_id = Column(Integer, primary_key=True, index=True)
    pi_name = Column(String, nullable=False)
    student_name = Column(String, nullable=False)
    usage = Column(Integer)
    soft_limit = Column(Integer)
    hard_limit = Column(Integer)
    files = Column(Integer)

# Database Model for Login History
class LoginHistoryDB(Base):
    """SQLAlchemy Model for storing login timestamps"""
    __tablename__ = "login_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, nullable=False)
    login_time = Column(DateTime, default=func.now())  # Automatically captures login timestamp


# New Database Model for Summary History
class SummaryHistoryDB(Base):
    """SQLAlchemy Model for storing summary history"""
    __tablename__ = "summary_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pi_name = Column(String, nullable=False)
    timestamp = Column(DateTime, default=func.now())  # Auto captures query time
    number_of_users = Column(Integer, nullable=False)
    total_usage = Column(Integer, nullable=False)
    usage_average = Column(Float, nullable=False)
    max_individual_usage = Column(Integer, nullable=False)


# Create the database tables
Base.metadata.create_all(bind=engine)

def init_db():
    """Initialize database with hardcoded users and quota data, preventing duplicates."""
    db = SessionLocal()
    
    # Check if users exist before inserting
    existing_users = {user.username for user in db.query(UserDB.username).all()}  # Fetch existing usernames
    
    test_users = [
    UserDB(username="amy", email="amy@example.com", hashed_password=pwd_context.hash("password123")),
    UserDB(username="bob", email="bob@example.com", hashed_password=pwd_context.hash("securepass")),
    UserDB(username="admin", email="admin@example.com", hashed_password=pwd_context.hash("adminpass"), is_admin=True),
    ]

    for user in test_users:
        if user.username not in existing_users:  # Avoid duplicates
            db.add(user)

    # Check if quotas exist before inserting
    existing_quotas = db.query(QuotaDB).count()  # If table is empty, insert data
    
    if existing_quotas == 0:  # Only insert if table is empty
        test_quotas = [
            QuotaDB(pi_name="amy", student_name="tom", usage=1, soft_limit=20, hard_limit=25, files=13),
            QuotaDB(pi_name="amy", student_name="amy", usage=3, soft_limit=20, hard_limit=25, files=13),
            QuotaDB(pi_name="amy", student_name="mary", usage=12, soft_limit=20, hard_limit=25, files=1401),
            QuotaDB(pi_name="bob", student_name="alice", usage=5, soft_limit=15, hard_limit=30, files=8),
        ]
        for quota in test_quotas:
            db.add(quota)

    db.commit()
    db.close()

init_db()  # Initialize with hardcoded data

# Pydantic Models
class Token(BaseModel):
    access_token: str
    token_type: str
    username: str
    email: str
    is_admin: bool

class TokenData(BaseModel):
    username: str | None = None

class User(BaseModel):
    username: str
    email: str | None = None
    disabled: bool | None = None

class UserInDB(User):
    hashed_password: str

# Dependency to Get Database Session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Utility Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db: Session, username: str):
    """Retrieve user from SQLAlchemy database"""
    return db.query(UserDB).filter(UserDB.username == username).first()

def authenticate_user(db: Session, username: str, password: str):
    """Verify user credentials"""
    user = get_user(db, username)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username")

    if not verify_password(password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc).isoformat()
    db.commit()

    return user

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    """Generate JWT token"""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def log_login(db: Session, username: str):
    """Insert a new login record into the login history table"""
    login_record = LoginHistoryDB(username=username)
    db.add(login_record)
    db.commit()

async def get_current_user(token: str = Depends(oauth_2_scheme), db: Session = Depends(get_db)):
    """Decode JWT token and return the current user"""
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credential_exception
        user = get_user(db, username)
        if user is None:
            raise credential_exception
    except JWTError:
        raise credential_exception

    return user

async def get_current_active_user(current_user: UserDB = Depends(get_current_user)):
    """Ensure user is active"""
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# API Endpoints

@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user, log the login, and return JWT token"""
    user = authenticate_user(db, form_data.username, form_data.password)

    if user:
        logger.info(f"User {user.username} authenticated successfully at {datetime.now(timezone.utc)}")

        # Log the login timestamp
        log_login(db, user.username)

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin
    }


@app.post("/api/login", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token"""
    user = authenticate_user(db, form_data.username, form_data.password)
    
    if user:
        logger.info(f"User {user.username} authenticated successfully at {datetime.now(timezone.utc)}")

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)


    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user.username,
        "email": user.email,
        "is_admin": user.is_admin
    }




@app.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Return the current logged-in user's info"""
    return current_user

@app.get("/debug/users/")
async def get_all_users(db: Session = Depends(get_db)):
    users = db.query(UserDB).all()
    return [{"username": user.username, "email": user.email} for user in users]

@app.get("/api/v2/members/")
async def get_members(current_user: UserDB = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Retrieve students under the currently logged-in PI from the database"""
    quotas = db.query(QuotaDB).filter(QuotaDB.pi_name == current_user.username).all()

    if not quotas:
        raise HTTPException(status_code=404, detail="No users found for this PI")

    members = {
        quota.student_name: {
            "usage": quota.usage,
            "soft": quota.soft_limit,
            "hard": quota.hard_limit,
            "files": quota.files
        }
        for quota in quotas
    }
    return {"PI Name": current_user.username, "Users": members}

@app.get("/api/v2/summary/history/")
async def get_summary_history(current_user: UserDB = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Retrieve all past summary queries."""
    summaries = db.query(SummaryHistoryDB).order_by(SummaryHistoryDB.timestamp.desc()).all()
    
    return [
        {
            "PI": record.pi_name,
            "Timestamp": record.timestamp.isoformat(),
            "Number of Users": record.number_of_users,
            "Total Usage": record.total_usage,
            "Usage Average": record.usage_average,
            "Max Individual Usage": record.max_individual_usage
        }
        for record in summaries
    ]

@app.get("/api/v2/admin/quotas/")
async def get_all_quotas(current_user: UserDB = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Allow admin to view all quota data across PIs."""
    if not current_user.is_admin:
        raise HTTPException(status_code=403, detail="Not authorized")

    quotas = db.query(QuotaDB).all()
    if not quotas:
        return []

    result = {}
    for quota in quotas:
        if quota.pi_name not in result:
            result[quota.pi_name] = {}
        result[quota.pi_name][quota.student_name] = {
            "usage": quota.usage,
            "soft": quota.soft_limit,
            "hard": quota.hard_limit,
            "files": quota.files
        }

    return result

@app.get("/api/v2/summary/")
async def get_summary(current_user: UserDB = Depends(get_current_active_user), db: Session = Depends(get_db)):
    """Retrieve summary quota usage for the currently logged-in PI and log the query."""
    quotas = db.query(QuotaDB).filter(QuotaDB.pi_name == current_user.username).all()

    if not quotas:
        raise HTTPException(status_code=404, detail="No quota records found for this PI")

    usages = [quota.usage for quota in quotas]

    summary_data = {
        "PI": current_user.username,
        "Number of Users": len(usages),
        "Total Usage": sum(usages),
        "Usage Average": sum(usages) / len(usages) if usages else 0,
        "Max Individual Usage": max(usages)
    }

    # Log the summary request in the database
    summary_entry = SummaryHistoryDB(
        pi_name=current_user.username,
        timestamp=datetime.now(timezone.utc),  # Ensure timestamp is recorded
        number_of_users=summary_data["Number of Users"],
        total_usage=summary_data["Total Usage"],
        usage_average=summary_data["Usage Average"],
        max_individual_usage=summary_data["Max Individual Usage"]
    )

    db.add(summary_entry)
    db.commit()

    return summary_data