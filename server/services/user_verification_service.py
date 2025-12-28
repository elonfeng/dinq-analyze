"""
User Verification Service

This module provides database operations for user verification system.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

# Import SQLAlchemy models
from src.models.user_verification import UserVerification, EmailVerification

# Import enums from the original models file
from server.models.user_verification import (
    UserType,
    VerificationStatus,
    VerificationStep
)
from server.utils.database import get_db_connection

# Configure logging
logger = logging.getLogger(__name__)

class UserVerificationService:
    """Service for user verification operations"""

    def __init__(self):
        """Initialize the service"""
        self.init_tables()

    def init_tables(self):
        """Initialize database tables"""
        try:
            # Tables are created automatically by SQLAlchemy when the models are imported
            # and create_tables() is called from src/utils/db_utils.py
            logger.info("User verification service initialized")
        except Exception as e:
            logger.error(f"Error initializing user verification service: {e}")
            raise

    def get_user_verification(self, user_id: str) -> Optional[UserVerification]:
        """Get user verification record"""
        try:
            with get_db_connection() as session:
                verification = session.query(UserVerification).filter(
                    UserVerification.user_id == user_id
                ).first()

                if verification:
                    # Detach from session to avoid session binding issues
                    session.expunge(verification)

                return verification
        except Exception as e:
            logger.error(f"Error getting user verification for {user_id}: {e}")
            raise

    def create_user_verification(self, user_id: str, user_type: str) -> UserVerification:
        """Create a new user verification record"""
        try:
            with get_db_connection() as session:
                verification = UserVerification(
                    user_id=user_id,
                    user_type=user_type,
                    current_step='basic_info',
                    verification_status='pending'
                )

                session.add(verification)
                session.commit()  # Commit to save to database
                session.refresh(verification)  # Refresh to get updated data

                # Detach from session to avoid session binding issues
                session.expunge(verification)

                logger.info(f"Created user verification record for {user_id} with type {user_type}")

                return verification
        except Exception as e:
            logger.error(f"Error creating user verification for {user_id}: {e}")
            raise

    def update_user_verification(self, user_id: str, data: Dict[str, Any]) -> UserVerification:
        """Update user verification record"""
        try:
            with get_db_connection() as session:
                # Get current record
                verification = session.query(UserVerification).filter(
                    UserVerification.user_id == user_id
                ).first()

                if not verification:
                    raise ValueError(f"User verification record not found for {user_id}")

                # Update fields
                for field, value in data.items():
                    if field in ['id', 'user_id', 'created_at']:
                        continue  # Skip these fields

                    if hasattr(verification, field):
                        setattr(verification, field, value)

                session.commit()  # Commit changes
                session.refresh(verification)  # Refresh to get updated data

                # Detach from session to avoid session binding issues
                session.expunge(verification)

                logger.info(f"Updated user verification for {user_id}")

                return verification
        except Exception as e:
            logger.error(f"Error updating user verification for {user_id}: {e}")
            raise

    def advance_step(self, user_id: str, next_step: str) -> UserVerification:
        """Advance user to next verification step"""
        try:
            return self.update_user_verification(user_id, {
                'current_step': next_step
            })
        except Exception as e:
            logger.error(f"Error advancing step for {user_id}: {e}")
            raise

    def complete_verification(self, user_id: str) -> UserVerification:
        """Mark verification as completed"""
        try:
            return self.update_user_verification(user_id, {
                'current_step': 'completed',
                'verification_status': 'verified',
                'completed_at': datetime.now()
            })
        except Exception as e:
            logger.error(f"Error completing verification for {user_id}: {e}")
            raise

    def get_verification_stats(self) -> Dict[str, Any]:
        """Get verification statistics"""
        try:
            with get_db_connection() as session:
                from sqlalchemy import func

                # Total verifications by type
                stats_by_type = session.query(
                    UserVerification.user_type,
                    UserVerification.verification_status,
                    func.count(UserVerification.id).label('count')
                ).group_by(
                    UserVerification.user_type,
                    UserVerification.verification_status
                ).all()

                # Current step distribution
                step_distribution = session.query(
                    UserVerification.current_step,
                    func.count(UserVerification.id).label('count')
                ).group_by(UserVerification.current_step).all()

                return {
                    'stats_by_type': [
                        {'user_type': row.user_type, 'verification_status': row.verification_status, 'count': row.count}
                        for row in stats_by_type
                    ],
                    'step_distribution': [
                        {'step': row.current_step, 'count': row.count}
                        for row in step_distribution
                    ]
                }
        except Exception as e:
            logger.error(f"Error getting verification stats: {e}")
            raise

class EmailVerificationService:
    """Service for email verification operations"""

    def __init__(self):
        """Initialize the service"""
        pass

    def create_verification_code(self, user_id: str, email: str, email_type: str) -> str:
        """Create a new email verification code"""
        import random
        import string

        try:
            # Generate 6-digit verification code
            verification_code = ''.join(random.choices(string.digits, k=6))

            # Set expiration time (15 minutes from now)
            expires_at = datetime.now() + timedelta(minutes=15)

            with get_db_connection() as session:
                # Invalidate any existing codes for this email
                session.query(EmailVerification).filter(
                    EmailVerification.user_id == user_id,
                    EmailVerification.email == email,
                    EmailVerification.email_type == email_type,
                    EmailVerification.verified_at.is_(None)
                ).update({'expires_at': datetime.now()})

                # Insert new verification code
                verification = EmailVerification(
                    user_id=user_id,
                    email=email,
                    email_type=email_type,
                    verification_code=verification_code,
                    expires_at=expires_at
                )

                session.add(verification)
                session.commit()  # Commit to save

                logger.info(f"Created verification code for {email} (type: {email_type})")
                return verification_code
        except Exception as e:
            logger.error(f"Error creating verification code for {email}: {e}")
            raise

    def verify_code(self, user_id: str, email: str, email_type: str, code: str) -> bool:
        """Verify email verification code"""
        try:
            with get_db_connection() as session:
                # Get the verification record
                verification = session.query(EmailVerification).filter(
                    EmailVerification.user_id == user_id,
                    EmailVerification.email == email,
                    EmailVerification.email_type == email_type,
                    EmailVerification.verification_code == code
                ).order_by(EmailVerification.created_at.desc()).first()

                if not verification:
                    logger.warning(f"Verification code not found for {email}")
                    return False

                # Check if already verified
                if verification.verified_at is not None:
                    logger.info(f"Email {email} already verified")
                    return True

                # Check if expired
                if verification.expires_at < datetime.now():
                    logger.warning(f"Verification code expired for {email}")
                    return False

                # Check attempts
                if verification.attempts >= verification.max_attempts:
                    logger.warning(f"Too many attempts for {email}")
                    return False

                # Increment attempts
                verification.attempts += 1

                # Mark as verified
                verification.verified_at = datetime.now()

                session.commit()  # Commit changes

                logger.info(f"Email {email} verified successfully")
                return True
        except Exception as e:
            logger.error(f"Error verifying code for {email}: {e}")
            raise

    def is_email_verified(self, user_id: str, email: str, email_type: str) -> bool:
        """Check if email is verified"""
        try:
            with get_db_connection() as session:
                verification = session.query(EmailVerification).filter(
                    EmailVerification.user_id == user_id,
                    EmailVerification.email == email,
                    EmailVerification.email_type == email_type,
                    EmailVerification.verified_at.isnot(None)
                ).order_by(EmailVerification.verified_at.desc()).first()

                return verification is not None
        except Exception as e:
            logger.error(f"Error checking email verification for {email}: {e}")
            return False

    def get_verification_history(self, user_id: str) -> List[EmailVerification]:
        """Get email verification history for user"""
        try:
            with get_db_connection() as session:
                verifications = session.query(EmailVerification).filter(
                    EmailVerification.user_id == user_id
                ).order_by(EmailVerification.created_at.desc()).all()

                # Detach all objects from session
                for verification in verifications:
                    session.expunge(verification)

                return verifications
        except Exception as e:
            logger.error(f"Error getting verification history for {user_id}: {e}")
            raise

    def verify_code_by_email(self, email: str, email_type: str, code: str) -> bool:
        """Verify email verification code by email (without user_id)"""
        try:
            with get_db_connection() as session:
                # Get the verification record by email and code
                verification = session.query(EmailVerification).filter(
                    EmailVerification.email == email,
                    EmailVerification.email_type == email_type,
                    EmailVerification.verification_code == code
                ).order_by(EmailVerification.created_at.desc()).first()

                if not verification:
                    logger.warning(f"Verification code not found for {email}")
                    return False

                # Check if already verified
                if verification.verified_at is not None:
                    logger.info(f"Email {email} already verified")
                    return True

                # Check if expired
                if verification.expires_at < datetime.now():
                    logger.warning(f"Verification code expired for {email}")
                    return False

                # Check attempts
                if verification.attempts >= verification.max_attempts:
                    logger.warning(f"Too many attempts for {email}")
                    return False

                # Increment attempts
                verification.attempts += 1

                # Mark as verified
                verification.verified_at = datetime.now()

                session.commit()  # Commit changes

                logger.info(f"Email {email} verified successfully via link")
                return True
        except Exception as e:
            logger.error(f"Error verifying code by email for {email}: {e}")
            raise

# Global service instances
user_verification_service = UserVerificationService()
email_verification_service = EmailVerificationService()
