"""
Authentication and authorization.
"""
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict
from app.config import get_logger, get_settings
from app.utils.exceptions import AuthenticationError

logger = get_logger(__name__)
settings = get_settings()


class AuthManager:
    """JWT-based authentication manager."""
    
    def __init__(self):
        """Initialize auth manager."""
        self.secret_key = settings.jwt_secret_key
        self.algorithm = "HS256"
        self.access_token_expire_minutes = 60
        
        logger.info("auth_manager_initialized")
    
    def create_access_token(
        self,
        user_id: str,
        additional_claims: Optional[Dict] = None
    ) -> str:
        """Create JWT access token.
        
        Args:
            user_id: User ID
            additional_claims: Optional additional claims
            
        Returns:
            JWT token string
        """
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "exp": expire,
            "iat": datetime.utcnow(),
            "type": "access"
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        
        logger.info("access_token_created", user_id=user_id)
        return token
    
    def verify_token(self, token: str) -> Dict:
        """Verify and decode JWT token.
        
        Args:
            token: JWT token string
            
        Returns:
            Decoded payload
            
        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm]
            )
            
            # Check token type
            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")
            
            return payload
        
        except jwt.ExpiredSignatureError:
            logger.warning("token_expired")
            raise AuthenticationError("Token has expired")
        
        except jwt.InvalidTokenError as e:
            logger.warning("invalid_token", error=str(e))
            raise AuthenticationError(f"Invalid token: {e}")
    
    def get_user_id_from_token(self, token: str) -> str:
        """Extract user ID from token.
        
        Args:
            token: JWT token
            
        Returns:
            User ID
            
        Raises:
            AuthenticationError: If token invalid
        """
        payload = self.verify_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise AuthenticationError("Token missing user ID")
        
        return user_id
    
    def create_anonymous_token(self) -> str:
        """Create token for anonymous user.
        
        Returns:
            JWT token
        """
        import uuid
        user_id = f"anon_{uuid.uuid4().hex[:8]}"
        return self.create_access_token(user_id, {"anonymous": True})


class APIKeyAuth:
    """API key-based authentication."""
    
    def __init__(self):
        """Initialize API key auth."""
        self.valid_keys = set(settings.api_keys) if settings.api_keys else set()
        
        if not self.valid_keys:
            logger.warning("no_api_keys_configured")
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key.
        
        Args:
            api_key: API key to verify
            
        Returns:
            True if valid
        """
        if not self.valid_keys:
            # If no keys configured, allow all (development mode)
            return True
        
        is_valid = api_key in self.valid_keys
        
        if not is_valid:
            logger.warning("invalid_api_key_attempt")
        
        return is_valid


# Global auth instances
_auth_manager: Optional[AuthManager] = None
_api_key_auth: Optional[APIKeyAuth] = None


def get_auth_manager() -> AuthManager:
    """Get global auth manager.
    
    Returns:
        AuthManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager


def get_api_key_auth() -> APIKeyAuth:
    """Get global API key auth.
    
    Returns:
        APIKeyAuth instance
    """
    global _api_key_auth
    if _api_key_auth is None:
        _api_key_auth = APIKeyAuth()
    return _api_key_auth
