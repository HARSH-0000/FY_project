from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from pydantic import BaseModel
from app.database import get_db
from app.services import auth
from app.core import logger
from typing import Optional

router = APIRouter()
security = HTTPBearer()


# Pydantic models
class UserSignUp(BaseModel):
    email: str
    username: str
    password: str
    full_name: Optional[str] = None


class UserSignIn(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: Optional[str]
    created_at: str


# Dependency to get current user from token
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """Get current user from JWT token."""
    token = credentials.credentials
    payload = auth.decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user_id = payload.get("sub")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
    
    user = auth.get_user_by_id(db, int(user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user"
        )
    
    return user


@router.post("/api/auth/signup", response_model=Token)
async def signup(user_data: UserSignUp, db: Session = Depends(get_db)):
    """Register a new user."""
    try:
        # Check if user already exists
        if auth.get_user_by_email(db, user_data.email):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        if auth.get_user_by_username(db, user_data.username):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
        
        # Create user
        user = auth.create_user(
            db=db,
            email=user_data.email,
            username=user_data.username,
            password=user_data.password,
            full_name=user_data.full_name
        )
        
        # Create access token
        access_token = auth.create_access_token(data={"sub": str(user.id)})
        
        # Update last login
        auth.update_last_login(db, user.id)
        
        logger.info(f"New user registered: {user.email}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signup failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed"
        )


@router.post("/api/auth/signin", response_model=Token)
async def signin(user_data: UserSignIn, db: Session = Depends(get_db)):
    """Sign in a user."""
    try:
        # Authenticate user
        user = auth.authenticate_user(db, user_data.email, user_data.password)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password"
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Inactive user"
            )
        
        # Create access token
        access_token = auth.create_access_token(data={"sub": str(user.id)})
        
        # Update last login
        auth.update_last_login(db, user.id)
        
        logger.info(f"User signed in: {user.email}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Signin failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sign in failed"
        )


@router.get("/api/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user = Depends(get_current_user)):
    """Get current user information."""
    created_at_str = current_user.created_at.isoformat() if hasattr(current_user.created_at, 'isoformat') else str(current_user.created_at or "")
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "full_name": current_user.full_name,
        "created_at": created_at_str
    }


@router.post("/api/auth/signout")
async def signout():
    """Sign out endpoint."""
    return {"message": "Signed out successfully"}

