"""
Cyberia Task API - TEK DOSYA VERSİYONU
Çalıştırma: uvicorn main:app --reload
Docs: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlmodel import Field, Session, SQLModel, create_engine, func, select
# ============================================================
# 1. VERİTABANI
# ============================================================
sqlite_url = "sqlite:///cyberia_data.db"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})
def get_session():
    with Session(engine) as session:
        yield session
def create_db_and_tables():
    SQLModel.metadata.create_all(engine)
# ============================================================
# 2. MODELLER (DB Tabloları)
# ============================================================
class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    hashed_password: str
    is_active: bool = Field(default=True)
class Task(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(index=True)
    description: Optional[str] = Field(default=None)
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner_id: int = Field(foreign_key="user.id", index=True)
# ============================================================
# 3. ŞEMALAR (Request / Response)
# ============================================================
class UserCreate(BaseModel):
    username: str
    password: str
class UserRead(BaseModel):
    id: int
    username: str
    is_active: bool
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[TaskStatus] = None
class TaskRead(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: TaskStatus
    created_at: datetime
    owner_id: int
class PaginatedTasks(BaseModel):
    total: int
    page: int
    limit: int
    items: List[TaskRead]
# ============================================================
# 4. AUTH (JWT + şifre hashleme)
# ============================================================
from dotenv import load_dotenv
import os

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
def authenticate_user(session: Session, username: str, password: str) -> Optional[User]:
    user = session.exec(select(User).where(User.username == username)).first()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user
def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Kimlik doğrulanamadı",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise credentials_exception
    return user
# ============================================================
# 5. CRUD İŞLEMLERİ
# ============================================================
def get_user_by_username(session: Session, username: str) -> Optional[User]:
    return session.exec(select(User).where(User.username == username)).first()
def create_user(session: Session, user_in: UserCreate) -> User:
    db_user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
    )
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
def create_task(session: Session, task_in: TaskCreate, owner_id: int) -> Task:
    db_task = Task(**task_in.dict(), owner_id=owner_id)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task
def get_task(session: Session, task_id: int, owner_id: int) -> Optional[Task]:
    statement = select(Task).where(Task.id == task_id, Task.owner_id == owner_id)
    return session.exec(statement).first()
def get_tasks(
    session: Session,
    owner_id: int,
    page: int = 1,
    limit: int = 10,
    status_filter: Optional[TaskStatus] = None,
    search: Optional[str] = None,
) -> Tuple[List[Task], int]:
    query = select(Task).where(Task.owner_id == owner_id)
    count_query = select(func.count()).select_from(Task).where(Task.owner_id == owner_id)
    if status_filter is not None:
        query = query.where(Task.status == status_filter)
        count_query = count_query.where(Task.status == status_filter)
    if search:
        query = query.where(Task.title.contains(search))
        count_query = count_query.where(Task.title.contains(search))
    total = session.exec(count_query).one()
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit).order_by(Task.created_at.desc())
    tasks = session.exec(query).all()
    return tasks, total
def update_task(session: Session, db_task: Task, task_in: TaskUpdate) -> Task:
    update_data = task_in.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_task, key, value)
    session.add(db_task)
    session.commit()
    session.refresh(db_task)
    return db_task
def delete_task(session: Session, db_task: Task) -> None:
    session.delete(db_task)
    session.commit()
# ============================================================
# 6. FASTAPI UYGULAMASI
# ============================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield
app = FastAPI(
    title="Cyberia Task API",
    description="JWT auth + CRUD + pagination + filtering destekli task yönetim API'si",
    version="1.0.0",
    lifespan=lifespan,
)
@app.get("/")
def root():
    return {"message": "Cyberia Task API çalışıyor. Detaylar için /docs adresine git."}
# ---------- AUTH ENDPOINTS ----------
@app.post("/auth/register", response_model=UserRead, status_code=status.HTTP_201_CREATED, tags=["auth"])
def register(user_in: UserCreate, session: Session = Depends(get_session)):
    existing = get_user_by_username(session, user_in.username)
    if existing:
        raise HTTPException(status_code=400, detail="Bu kullanıcı adı zaten alınmış")
    return create_user(session, user_in)
@app.post("/auth/login", response_model=Token, tags=["auth"])
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
):
    user = authenticate_user(session, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.username})
    return Token(access_token=access_token)
# ---------- TASK ENDPOINTS ----------
@app.post("/tasks/", response_model=TaskRead, status_code=status.HTTP_201_CREATED, tags=["tasks"])
def create_task_endpoint(
    task_in: TaskCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    return create_task(session, task_in, owner_id=current_user.id)
@app.get("/tasks/", response_model=PaginatedTasks, tags=["tasks"])
def list_tasks_endpoint(
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=10, ge=1, le=100),
    status_filter: Optional[TaskStatus] = Query(default=None, alias="status"),
    search: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    /tasks/?page=1&limit=10
    /tasks/?status=done
    /tasks/?search=rapor
    """
    tasks, total = get_tasks(
        session,
        owner_id=current_user.id,
        page=page,
        limit=limit,
        status_filter=status_filter,
        search=search,
    )
    return PaginatedTasks(total=total, page=page, limit=limit, items=tasks)
@app.get("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def read_task_endpoint(
    task_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_task = get_task(session, task_id, owner_id=current_user.id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    return db_task
@app.put("/tasks/{task_id}", response_model=TaskRead, tags=["tasks"])
def update_task_endpoint(
    task_id: int,
    task_in: TaskUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_task = get_task(session, task_id, owner_id=current_user.id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    return update_task(session, db_task, task_in)
@app.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tasks"])
def delete_task_endpoint(
    task_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    db_task = get_task(session, task_id, owner_id=current_user.id)
    if not db_task:
        raise HTTPException(status_code=404, detail="Task bulunamadı")
    delete_task(session, db_task)
    return None
