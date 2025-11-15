import os
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.exc import OperationalError

# ----------------------------------------------------------------------
# 1. DATABASE CONFIGURATION
# ----------------------------------------------------------------------

# **CONNECTION DETAILS:** Using the URL provided by you.
# postgresql://braguser:new@localhost:5432/bragdboard
SQLALCHEMY_DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://braguser:new@localhost:5432/bragdboard"
)

# Initialize engine, session, and base outside of try block
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ----------------------------------------------------------------------
# 2. SQLALCHEMY DATABASE MODEL
# ----------------------------------------------------------------------

class Employee(Base):
    """Table definition for employee user data."""
    __tablename__ = "employees"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # In a real app, always store HASHED passwords, not plain text!
    password_hash = Column(String, nullable=False) 
    department = Column(String, nullable=False)


# ----------------------------------------------------------------------
# 3. Pydantic Models for Data Validation
# ----------------------------------------------------------------------

class SignupRequest(BaseModel):
    """Data model for the incoming signup request from the React frontend."""
    email: EmailStr # Ensures the input is a valid email format
    password: str
    department: str

class SignupResponse(BaseModel):
    """Data model for the API response."""
    message: str
    employee_id: int
    email: EmailStr
    department: str

# ----------------------------------------------------------------------
# 4. FASTAPI SETUP
# ----------------------------------------------------------------------

app = FastAPI(title="Recognition+ Authentication API")

# Setup CORS middleware 
origins = [
    "http://localhost:3000", # Common React default port
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Dependency to get a new database session for each request
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ----------------------------------------------------------------------
# 5. LIFECYCLE HOOK: CHECK DATABASE CONNECTION ON STARTUP
# ----------------------------------------------------------------------

@app.on_event("startup")
def startup_db_check():
    """
    Explicitly test the database connection and create tables on startup.
    This provides immediate feedback if credentials or permissions are wrong.
    """
    print("Attempting database connection and table creation...")
    try:
        # Test the connection immediately
        with engine.connect() as connection:
            print("Successfully connected to PostgreSQL database.")
            
        # Create the database tables if they don't exist
        Base.metadata.create_all(bind=engine)
        print("Database tables ensured (employees table created/checked).")

    except OperationalError as e:
        # If connection fails (wrong password, server down, etc.)
        print("\n" + "="*80)
        print("!!! CRITICAL POSTGRESQL CONNECTION ERROR !!!")
        print(f"Error: {e}")
        print("Check your PostgreSQL server status and 'braguser' credentials.")
        print("If the server is running, the URL or password is still incorrect.")
        print("="*80 + "\n")
        
    except Exception as e:
        # Catch permission errors (InsufficientPrivilege) or others
        print("\n" + "="*80)
        print("!!! CRITICAL DATABASE ERROR ON STARTUP !!!")
        print(f"Error: {e}")
        print("If this is a 'Permission Denied' error, you must run the following in PgAdmin:")
        print("GRANT ALL PRIVILEGES ON SCHEMA public TO braguser;")
        print("="*80 + "\n")


# ----------------------------------------------------------------------
# 6. API ENDPOINT
# ----------------------------------------------------------------------

@app.post("/api/signup", response_model=SignupResponse)
def signup_employee(data: SignupRequest, db: Session = Depends(get_db)):
    """
    Handles the signup logic: checks existence, creates a new employee, 
    and saves the record to the PostgreSQL database.
    """
    
    # 1. Check if user already exists
    if db.query(Employee).filter(Employee.email == data.email).first():
        raise HTTPException(
            status_code=400, 
            detail="Account with this email already exists."
        )

    # 2. Create and save new employee
    # NOTE: In a REAL app, use a secure library (like `passlib`) to hash the password.
    new_employee = Employee(
        email=data.email,
        password_hash=data.password, 
        department=data.department
    )

    db.add(new_employee)
    db.commit()
    db.refresh(new_employee) # Refresh to get the generated 'id'

    return {
        "message": "Success! Account created and data saved to PostgreSQL.",
        "employee_id": new_employee.id,
        "email": new_employee.email,
        "department": new_employee.department
    }

# Health Check endpoint
@app.get("/health")
def health_check():
    return {"status": "ok", "service": "FastAPI Backend"}

# Root endpoint (to resolve the 404 Not Found issue for GET /)
@app.get("/")
def read_root():
    """A friendly message to confirm the API is running."""
    return {"message": "Welcome to the Recognition+ API. Visit /docs for endpoints."}
