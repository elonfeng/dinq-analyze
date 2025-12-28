"""
Base database models and connection setup.
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# Create base model class
Base = declarative_base()

# Define ApiUsage model for tracking API usage
class ApiUsage(Base):
    """
    ApiUsage model for tracking API calls to expensive endpoints.
    Used for analytics, billing, and rate limiting.
    """
    __tablename__ = 'api_usage'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who made the API call")
    endpoint = Column(String(100), nullable=False, index=True, comment="API endpoint that was called")
    query = Column(Text, nullable=True, comment="The query parameter used in the API call")
    query_type = Column(String(50), nullable=True, comment="Type of query (e.g., 'scholar_name', 'scholar_id')")
    scholar_id = Column(String(50), nullable=True, index=True, comment="Scholar ID if available")
    status = Column(String(20), nullable=False, default="success", comment="Status of the API call (success, error)")
    error_message = Column(Text, nullable=True, comment="Error message if the call failed")
    execution_time = Column(Float, nullable=True, comment="Execution time in seconds")
    ip_address = Column(String(50), nullable=True, comment="IP address of the client")
    user_agent = Column(String(255), nullable=True, comment="User agent of the client")
    created_at = Column(DateTime, default=func.now(), comment="Timestamp when the record was created")

    def __repr__(self):
        return f"<ApiUsage(id={self.id}, user_id='{self.user_id}', endpoint='{self.endpoint}', created_at='{self.created_at}')>"

# Define Scholar model for caching scholar information
class Scholar(Base):
    """
    Scholar model for storing Google Scholar researcher information.
    """
    __tablename__ = 'scholars'

    id = Column(Integer, primary_key=True, autoincrement=True)
    scholar_id = Column(String(20), unique=True, nullable=False, index=True, comment="Google Scholar ID")
    name = Column(String(100), nullable=False, index=True, comment="Full name of the researcher")
    affiliation = Column(String(200), nullable=True, comment="Current affiliation/institution")
    email = Column(String(100), nullable=True, comment="Email address if available")
    research_fields = Column(JSON, nullable=True, comment="Research interests/fields")
    total_citations = Column(Integer, nullable=True, comment="Total citation count")
    h_index = Column(Integer, nullable=True, comment="H-index value")
    i10_index = Column(Integer, nullable=True, comment="i10-index value")
    profile_data = Column(JSON, nullable=True, comment="Full profile data in JSON format")
    publications_data = Column(JSON, nullable=True, comment="Publications data in JSON format")
    coauthors_data = Column(JSON, nullable=True, comment="Co-authors data in JSON format")
    report_data = Column(JSON, nullable=True, comment="Generated report data in JSON format")
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    created_at = Column(DateTime, default=func.now(), comment="Record creation timestamp")

    def __repr__(self):
        return f"<Scholar(id={self.id}, name='{self.name}', scholar_id='{self.scholar_id}')>"

# Define LinkedIn model for caching LinkedIn profile information
class LinkedInProfile(Base):
    """
    LinkedInProfile model for storing LinkedIn profile information.
    """
    __tablename__ = 'linkedin_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    linkedin_id = Column(String(100), unique=True, nullable=False, index=True, comment="LinkedIn profile ID")
    person_name = Column(String(100), nullable=False, index=True, comment="Full name of the person")
    linkedin_url = Column(String(500), nullable=True, comment="LinkedIn profile URL")
    profile_data = Column(JSON, nullable=True, comment="Full profile data in JSON format")
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    created_at = Column(DateTime, default=func.now(), comment="Record creation timestamp")

    def __repr__(self):
        return f"<LinkedInProfile(id={self.id}, name='{self.person_name}', linkedin_id='{self.linkedin_id}')>"


# Define HuggingFace model for caching HuggingFace profile information
class HuggingFaceProfile(Base):
    """
    HuggingFaceProfile model for storing HuggingFace profile information.
    """
    __tablename__ = 'huggingface_profiles'

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False, index=True, comment="HuggingFace username")
    profile = Column(JSON, nullable=True, comment="Full profile data in JSON format")
    user_id = Column(String(100), nullable=True, index=True, comment="User ID who requested this analysis")
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Last update timestamp")
    created_at = Column(DateTime, default=func.now(), comment="Record creation timestamp")

    def __repr__(self):
        return f"<HuggingFaceProfile(id={self.id}, username='{self.username}', user_id='{self.user_id}')>"

# Define ActivationCode model for user activation
class ActivationCode(Base):
    """
    ActivationCode model for storing user activation codes.
    Each code can only be used once by a single user.
    """
    __tablename__ = 'activation_codes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(6), unique=True, nullable=False, index=True, comment="Unique activation code (6 characters)")
    is_used = Column(Boolean, default=False, nullable=False, index=True, comment="Whether the code has been used")
    created_by = Column(String(100), nullable=True, comment="User ID who created this code")
    used_by = Column(String(100), nullable=True, index=True, comment="User ID who used this code")
    created_at = Column(DateTime, default=func.now(), comment="When the code was created")
    used_at = Column(DateTime, nullable=True, comment="When the code was used")
    expires_at = Column(DateTime, nullable=True, comment="When the code expires (optional)")
    batch_id = Column(String(50), nullable=True, index=True, comment="Batch identifier for bulk code generation")
    notes = Column(Text, nullable=True, comment="Additional notes or purpose of this code")

    def __repr__(self):
        status = "Used" if self.is_used else "Available"
        return f"<ActivationCode(code='{self.code}', status='{status}', created_at='{self.created_at}')>"

# Define User model for storing user information
class User(Base):
    """
    User model for storing user information.
    """
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True, comment="Unique user identifier (from auth system)")
    display_name = Column(String(100), nullable=True, comment="User's display name")
    email = Column(String(100), nullable=True, comment="User's email address")
    profile_picture = Column(String(255), nullable=True, comment="URL to user's profile picture")
    is_activated = Column(Boolean, default=False, nullable=False, comment="Whether the user has used an activation code")
    activation_code = Column(String(6), nullable=True, comment="The activation code used by the user")
    activated_at = Column(DateTime, nullable=True, comment="When the user was activated")
    user_type = Column(String(20), default="standard", nullable=False, comment="User type (standard, premium, admin, etc.)")
    preferences = Column(JSON, nullable=True, comment="User preferences in JSON format")
    last_login = Column(DateTime, nullable=True, comment="Last login timestamp")
    created_at = Column(DateTime, default=func.now(), comment="When the user was created")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="When the user was last updated")

    def __repr__(self):
        return f"<User(id={self.id}, user_id='{self.user_id}', display_name='{self.display_name}', is_activated={self.is_activated})>"

# Define WaitingList model for storing waiting list entries
class WaitingList(Base):
    """
    WaitingList model for storing waiting list entries.
    """
    __tablename__ = 'waiting_list'

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), unique=True, nullable=False, index=True, comment="User ID (from auth system)")
    email = Column(String(100), nullable=False, index=True, comment="User's email address")
    name = Column(String(100), nullable=False, comment="User's full name")
    organization = Column(String(100), nullable=True, comment="User's organization or company")
    job_title = Column(String(100), nullable=True, comment="User's job title")
    reason = Column(Text, nullable=True, comment="Reason for joining the waiting list")
    status = Column(String(20), default="pending", nullable=False, index=True, comment="Status (pending, approved, rejected)")
    extra_data = Column(JSON, nullable=True, comment="Additional metadata in JSON format")
    created_at = Column(DateTime, default=func.now(), comment="When the entry was created")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="When the entry was last updated")
    approved_at = Column(DateTime, nullable=True, comment="When the entry was approved")
    approved_by = Column(String(100), nullable=True, comment="User ID who approved the entry")

    def __repr__(self):
        return f"<WaitingList(id={self.id}, user_id='{self.user_id}', email='{self.email}', status='{self.status}')>"

# Define WaitingList model for storing waiting list entries
class WebCache(Base):
    """
    WebCache model for storing html.
    """
    __tablename__ = 'web_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    uuid = Column(String(100), nullable=False, index=True, comment="scholar:scholarId, github:username, scholar_compare:scholar1Id&&scholar2Id, github_compare:username1&&username2")
    content = Column(Text, nullable=True, comment="html content")
    type = Column(String(20), default="scholar", nullable=False, index=True, comment="Status (scholar, github, sholar_compare, github_compare)")
    created_at = Column(DateTime, default=func.now(), comment="When the entry was created")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="When the entry was last updated")

    def __repr__(self):
        return f"<WebCache(id={self.id}, content='{self.content}', type='{self.type}', status='{self.type}')>"
    
class Article(Base):
    __tablename__ = 'article'
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    teaser = Column(String(255))
    excerpt = Column(Text)
    published_at = Column(DateTime)
    updated_at = Column(DateTime)
    slug = Column(String(128), unique=True, nullable=False)
    view_count = Column(Integer, default=0)
    authors = Column(Text)  # 新增，存逗号分隔字符串

class Author(Base):
    __tablename__ = 'author'
    id = Column(Integer, primary_key=True, autoincrement=True)

# Unified analysis job models (rule-driven pipeline)
class AnalysisJob(Base):
    """
    AnalysisJob model for unified analysis pipeline jobs.
    """
    __tablename__ = 'jobs'

    id = Column(String(64), primary_key=True, comment="Job ID (uuid hex)")
    user_id = Column(String(100), nullable=False, index=True, comment="User ID who created the job")
    source = Column(String(50), nullable=False, index=True, comment="Source type (scholar/github/linkedin/...)")
    status = Column(String(20), nullable=False, default="queued", index=True, comment="queued|running|completed|partial|failed|cancelled")
    last_seq = Column(Integer, nullable=False, default=0, comment="Last emitted job_events.seq (for resume)")
    input = Column(JSON, nullable=True, comment="Original input payload")
    options = Column(JSON, nullable=True, comment="Analysis options (cache, priority, etc.)")
    result = Column(JSON, nullable=True, comment="Final aggregated result (optional)")
    subject_key = Column(String(256), nullable=True, index=True, comment="Canonical subject key (for cross-job caching)")
    created_at = Column(DateTime, default=func.now(), comment="Job creation timestamp")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Job update timestamp")


class AnalysisSubject(Base):
    """
    Canonical analyzed entity (source + subject_key).

    Examples:
      - (github, "login:torvalds")
      - (scholar, "id:Y-ql3zMAAAAJ")
      - (linkedin, "url:https://www.linkedin.com/in/...")
    """

    __tablename__ = "analysis_subjects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source = Column(String(50), nullable=False, index=True)
    subject_key = Column(String(256), nullable=False, index=True)
    canonical_input = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AnalysisArtifactCache(Base):
    """
    Cross-job artifact cache for analysis outputs.

    Keyed by a deterministic artifact_key (typically derived from subject + pipeline version + options).
    """

    __tablename__ = "analysis_artifact_cache"

    artifact_key = Column(String(128), primary_key=True, comment="Deterministic key (sha256 hex)")
    kind = Column(String(64), nullable=False, index=True, comment="full_report|card:<type>|resource:<name>|...")
    payload = Column(JSON, nullable=True)
    content_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True, index=True)
    meta = Column(JSON, nullable=True)


class AnalysisRun(Base):
    """
    Reusable analysis run snapshot for a subject.

    Used for stale-while-revalidate and cross-job reuse to avoid repeated expensive analysis.
    """

    __tablename__ = "analysis_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("analysis_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_version = Column(String(64), nullable=False, index=True)
    options_hash = Column(String(128), nullable=False, index=True)
    status = Column(String(20), nullable=False, default="running", index=True, comment="running|completed|failed")
    fingerprint = Column(String(128), nullable=True, comment="Optional external change fingerprint")
    full_report_artifact_key = Column(String(128), ForeignKey("analysis_artifact_cache.artifact_key", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=func.now())
    started_at = Column(DateTime, default=func.now())
    ended_at = Column(DateTime, nullable=True)
    freshness_until = Column(DateTime, nullable=True, index=True)
    meta = Column(JSON, nullable=True)


class AnalysisResourceVersion(Base):
    """
    Optional resource-level caching (raw/normalized data snapshots per subject).

    This enables incremental refresh: only recompute derived artifacts when the underlying
    resource hash changes.
    """

    __tablename__ = "analysis_resource_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    subject_id = Column(Integer, ForeignKey("analysis_subjects.id", ondelete="CASCADE"), nullable=False, index=True)
    resource_name = Column(String(64), nullable=False, index=True)
    fetch_params_hash = Column(String(128), nullable=False)
    content_hash = Column(String(128), nullable=True)
    etag = Column(Text, nullable=True)
    last_modified = Column(Text, nullable=True)
    fetched_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=True, index=True)
    payload = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)


class AnalysisJobCard(Base):
    """
    AnalysisJobCard model for card-level tasks within a job.
    """
    __tablename__ = 'job_cards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    card_type = Column(String(50), nullable=False, index=True, comment="Card type name")
    priority = Column(Integer, nullable=False, default=0, index=True, comment="Higher runs earlier (scheduler)")
    status = Column(String(20), nullable=False, default="pending", index=True, comment="pending|ready|running|completed|failed|skipped|timeout")
    deadline_ms = Column(Integer, nullable=True, comment="Soft deadline (ms since job creation) to start this card")
    concurrency_group = Column(String(64), nullable=True, index=True, comment="Concurrency group for runner budgeting (llm/github_api/...)")
    input = Column(JSON, nullable=True, comment="Card-specific input data")
    deps = Column(JSON, nullable=True, comment="Card dependencies (list of card_type)")
    output = Column(JSON, nullable=True, comment="Card output data")
    retry_count = Column(Integer, nullable=False, default=0, comment="Retry attempts")
    started_at = Column(DateTime, nullable=True, comment="Card start time")
    ended_at = Column(DateTime, nullable=True, comment="Card end time")
    created_at = Column(DateTime, default=func.now(), comment="Creation timestamp")
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), comment="Update timestamp")


class AnalysisJobEvent(Base):
    """
    AnalysisJobEvent model for streaming/replay events.
    """
    __tablename__ = 'job_events'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey('job_cards.id', ondelete='SET NULL'), nullable=True, index=True)
    seq = Column(Integer, nullable=False, comment="Monotonic event sequence per job")
    event_type = Column(String(50), nullable=False, comment="job.started|card.started|card.delta|card.completed|...") 
    payload = Column(JSON, nullable=True, comment="Event payload")
    created_at = Column(DateTime, default=func.now(), comment="Event timestamp")


class AnalysisArtifact(Base):
    """
    AnalysisArtifact model for storing generated artifacts (optional).
    """
    __tablename__ = 'artifacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64), ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    card_id = Column(Integer, ForeignKey('job_cards.id', ondelete='SET NULL'), nullable=True, index=True)
    type = Column(String(50), nullable=False, comment="artifact type")
    payload = Column(JSON, nullable=True, comment="Artifact payload")
    file_url = Column(Text, nullable=True, comment="Optional file URL")
    created_at = Column(DateTime, default=func.now(), comment="Creation timestamp")


class AnalysisJobIdempotency(Base):
    """
    Idempotency mapping for create-job requests.

    Uniqueness is enforced per (user_id, idempotency_key) so clients can safely retry
    without creating duplicate jobs.
    """

    __tablename__ = "job_idempotency"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False, index=True, comment="User ID")
    idempotency_key = Column(String(128), nullable=False, comment="Idempotency key from client")
    request_hash = Column(String(128), nullable=False, comment="Hash of normalized create payload")
    job_id = Column(String(64), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=func.now(), comment="Creation timestamp")


class LLMCache(Base):
    """
    LLM cache entries for prompt+model responses.
    """
    __tablename__ = 'llm_cache'

    id = Column(Integer, primary_key=True, autoincrement=True)
    cache_key = Column(String(128), unique=True, nullable=False, index=True, comment="Hash of model+messages")
    response_text = Column(Text, nullable=False, comment="LLM response content")
    created_at = Column(DateTime, default=func.now(), comment="Creation timestamp")

class ArticleAuthor(Base):
    __tablename__ = 'article_author'
    id = Column(Integer, primary_key=True, autoincrement=True)
    article_id = Column(Integer, ForeignKey('article.id'), nullable=False)
    author_id = Column(Integer, ForeignKey('author.id'), nullable=False)

class TalentMove(Base):
    __tablename__ = 'talent_move'
    id = Column(Integer, primary_key=True, autoincrement=True)
    person_name = Column(String(128))
    from_company = Column(String(128))
    to_company = Column(String(128))
    salary = Column(String(128))
    avatar_url = Column(String(256))
    post_image_url = Column(String(256))
    tweet_url = Column(String(256))
    query = Column(String(256))
    created_at = Column(DateTime)
    talent_description = Column(Text)  # 新增人才描述字段
    age = Column(Integer)
    work_experience = Column(Text)
    education = Column(Text)
    major_achievement = Column(Text)
    like_count = Column(Integer, default=0)  # 新增点赞数量字段
    from_company_logo_url = Column(String(256))  # 新增来源公司logo URL
    to_company_logo_url = Column(String(256))  # 新增目标公司logo URL

class TalentMoveLike(Base):
    """
    人才流动点赞表
    记录用户对人才流动信息的点赞
    """
    __tablename__ = 'talent_move_likes'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    talent_move_id = Column(Integer, ForeignKey('talent_move.id'), nullable=False, index=True, comment="人才流动记录ID")
    user_id = Column(String(100), nullable=False, index=True, comment="用户ID")
    created_at = Column(DateTime, default=func.now(), comment="点赞时间")
    
    def __repr__(self):
        return f"<TalentMoveLike(id={self.id}, talent_move_id={self.talent_move_id}, user_id='{self.user_id}')>"
