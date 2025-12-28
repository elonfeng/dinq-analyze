"""
File Upload API

This module provides API endpoints for uploading files (images, PDFs, documents) to Supabase storage.
"""

import uuid
import logging
from flask import Blueprint, request, jsonify, g
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage

# Import authentication utilities
from server.utils.auth import require_verified_user

# Import Supabase client
from server.utils.supabase_client import get_supabase_client

# Create blueprint
image_upload_bp = Blueprint('image_upload', __name__, url_prefix='/api')

# Configure logging
logger = logging.getLogger(__name__)

# Allowed file extensions - Images, PDFs, and Documents
ALLOWED_EXTENSIONS = {
    # Images
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'ico',
    # Documents
    'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt',
    # Spreadsheets
    'xls', 'xlsx', 'csv', 'ods',
    # Presentations
    'ppt', 'pptx', 'odp',
    # Archives
    'zip', 'rar', '7z', 'tar', 'gz',
    # Other
    'json', 'xml', 'yaml', 'yml'
}

# File type categories for better organization
FILE_CATEGORIES = {
    'images': {'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff', 'ico'},
    'documents': {'pdf', 'doc', 'docx', 'txt', 'rtf', 'odt'},
    'spreadsheets': {'xls', 'xlsx', 'csv', 'ods'},
    'presentations': {'ppt', 'pptx', 'odp'},
    'archives': {'zip', 'rar', '7z', 'tar', 'gz'},
    'data': {'json', 'xml', 'yaml', 'yml'}
}

# Maximum file size (5MB)
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB in bytes

def allowed_file(filename: str) -> bool:
    """
    Check if the file extension is allowed.

    Args:
        filename: The filename to check

    Returns:
        True if the file extension is allowed, False otherwise
    """
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def get_file_category(filename: str) -> str:
    """
    Get the category of a file based on its extension.

    Args:
        filename: The filename to categorize

    Returns:
        The file category (images, documents, etc.) or 'other'
    """
    if not filename or '.' not in filename:
        return 'other'

    extension = filename.rsplit('.', 1)[1].lower()

    for category, extensions in FILE_CATEGORIES.items():
        if extension in extensions:
            return category

    return 'other'

def format_file_size(size_bytes: int) -> str:
    """
    Format file size in human readable format.

    Args:
        size_bytes: Size in bytes

    Returns:
        Formatted size string
    """
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"

def validate_file(file: FileStorage) -> tuple[bool, str]:
    """
    Validate the uploaded file.

    Args:
        file: The uploaded file

    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file:
        return False, "No file provided"

    if file.filename == '':
        return False, "No file selected"

    if not allowed_file(file.filename):
        # Group extensions by category for better error message
        categories = []
        for category, extensions in FILE_CATEGORIES.items():
            ext_list = ', '.join(sorted(extensions))
            categories.append(f"{category.title()}: {ext_list}")

        error_msg = f"File type not allowed. Supported file types:\n" + "\n".join(categories)
        return False, error_msg

    # Check file size (we'll read the content to check size)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning

    if file_size == 0:
        return False, "File is empty"

    if file_size > MAX_FILE_SIZE:
        max_size_mb = MAX_FILE_SIZE / (1024 * 1024)
        current_size = format_file_size(file_size)
        return False, f"File too large ({current_size}). Maximum size: {max_size_mb}MB"

    return True, ""

@image_upload_bp.route('/upload-image', methods=['POST', 'OPTIONS'])
@require_verified_user
def upload_image():
    """
    Upload a file (image, PDF, document, etc.) to Supabase storage.

    Expected form data:
    - file: The file to upload (images, PDFs, documents, etc.)
    - bucket: (optional) The storage bucket name, defaults to 'demo'
    - folder: (optional) The folder path within the bucket

    Supported file types:
    - Images: png, jpg, jpeg, gif, webp, svg, bmp, tiff, ico
    - Documents: pdf, doc, docx, txt, rtf, odt
    - Spreadsheets: xls, xlsx, csv, ods
    - Presentations: ppt, pptx, odp
    - Archives: zip, rar, 7z, tar, gz
    - Data: json, xml, yaml, yml

    Maximum file size: 5MB

    Returns:
        JSON response with the uploaded file information
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        # Get user ID from authentication
        user_id = g.user_id
        logger.info(f"File upload request from user: {user_id}")

        # Check if file is in request
        if 'file' not in request.files:
            return jsonify({
                'error': 'No file part in the request',
                'success': False
            }), 400

        file = request.files['file']

        # Validate file
        is_valid, error_message = validate_file(file)
        if not is_valid:
            return jsonify({
                'error': error_message,
                'success': False
            }), 400

        # Get optional parameters
        bucket_name = request.form.get('bucket', 'demo')
        folder_path = request.form.get('folder', '')

        # Get file category for better organization
        file_category = get_file_category(file.filename)

        # Secure the filename and add UUID to prevent conflicts
        original_filename = secure_filename(file.filename)
        file_extension = original_filename.rsplit('.', 1)[1].lower()
        unique_filename = f"{uuid.uuid4().hex}.{file_extension}"

        # Construct the full path
        if folder_path:
            # Ensure folder path doesn't start or end with '/'
            folder_path = folder_path.strip('/')
            file_path = f"{folder_path}/{unique_filename}"
        else:
            file_path = unique_filename

        # Add user ID to the path for organization
        file_path = f"users/{user_id}/{file_path}"

        # Get Supabase client
        supabase = get_supabase_client()

        # Read file content
        file_content = file.read()

        # Upload to Supabase storage
        logger.info(f"Uploading file to bucket '{bucket_name}' with path '{file_path}'")

        try:
            response = supabase.storage.from_(bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": file.content_type,
                    "cache-control": "3600",
                    "upsert": False  # Don't overwrite existing files
                }
            )

            # Check for upload errors
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase upload error: {response.error}")
                return jsonify({
                    'error': f'Upload failed: {response.error}',
                    'success': False
                }), 500
        except Exception as upload_error:
            logger.error(f"Upload exception: {upload_error}")
            return jsonify({
                'error': f'Upload failed: {str(upload_error)}',
                'success': False
            }), 500

        # Get the public URL for the uploaded file
        try:
            public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
        except Exception as url_error:
            logger.error(f"Error getting public URL: {url_error}")
            public_url = f"https://rlkbxuuszlscnwagrsyx.supabase.co/storage/v1/object/public/{bucket_name}/{file_path}"

        # Prepare response data
        upload_data = {
            'success': True,
            'data': {
                'id': getattr(response, 'data', {}).get('id') if hasattr(response, 'data') else None,
                'path': file_path,
                'fullPath': getattr(response, 'data', {}).get('fullPath') if hasattr(response, 'data') else file_path,
                'publicUrl': public_url,
                'bucket': bucket_name,
                'originalFilename': original_filename,
                'filename': unique_filename,
                'extension': file_extension,
                'category': file_category,
                'size': len(file_content),
                'sizeFormatted': format_file_size(len(file_content)),
                'contentType': file.content_type,
                'uploadedBy': user_id,
                'folder': folder_path if folder_path else None
            }
        }

        logger.info(f"File uploaded successfully: {file_path}")
        logger.info(f"Public URL: {public_url}")

        return jsonify(upload_data), 200

    except Exception as e:
        logger.error(f"Error uploading image: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500

@image_upload_bp.route('/delete-image', methods=['DELETE', 'OPTIONS'])
@require_verified_user
def delete_image():
    """
    Delete an image from Supabase storage.

    Expected JSON data:
    - path: The file path to delete
    - bucket: (optional) The storage bucket name, defaults to 'images'

    Returns:
        JSON response with the deletion status
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'DELETE, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        # Get user ID from authentication
        user_id = g.user_id
        logger.info(f"Image deletion request from user: {user_id}")

        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({
                'error': 'No JSON data provided',
                'success': False
            }), 400

        file_path = data.get('path')
        if not file_path:
            return jsonify({
                'error': 'File path is required',
                'success': False
            }), 400

        bucket_name = data.get('bucket', 'demo')

        # Security check: ensure user can only delete their own files
        if not file_path.startswith(f"users/{user_id}/"):
            return jsonify({
                'error': 'You can only delete your own files',
                'success': False
            }), 403

        # Get Supabase client
        supabase = get_supabase_client()

        # Delete from Supabase storage
        logger.info(f"Deleting file from bucket '{bucket_name}' with path '{file_path}'")

        try:
            response = supabase.storage.from_(bucket_name).remove([file_path])

            # Check for deletion errors
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase deletion error: {response.error}")
                return jsonify({
                    'error': f'Deletion failed: {response.error}',
                    'success': False
                }), 500
        except Exception as delete_error:
            logger.error(f"Delete exception: {delete_error}")
            return jsonify({
                'error': f'Deletion failed: {str(delete_error)}',
                'success': False
            }), 500

        logger.info(f"File deleted successfully: {file_path}")

        return jsonify({
            'success': True,
            'message': 'File deleted successfully',
            'data': {
                'path': file_path,
                'bucket': bucket_name
            }
        }), 200

    except Exception as e:
        logger.error(f"Error deleting image: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500

@image_upload_bp.route('/list-images', methods=['GET', 'OPTIONS'])
@require_verified_user
def list_images():
    """
    List files uploaded by the current user.

    Query parameters:
    - bucket: (optional) The storage bucket name, defaults to 'demo'
    - folder: (optional) The folder path within the user's directory
    - limit: (optional) Maximum number of files to return, defaults to 50

    Returns:
        JSON response with the list of user's files
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        # Get user ID from authentication
        user_id = g.user_id
        logger.info(f"Image list request from user: {user_id}")

        # Get query parameters
        bucket_name = request.args.get('bucket', 'demo')
        folder_path = request.args.get('folder', '')
        limit = min(int(request.args.get('limit', 50)), 100)  # Cap at 100

        # Construct the user's directory path
        user_path = f"users/{user_id}"
        if folder_path:
            folder_path = folder_path.strip('/')
            user_path = f"{user_path}/{folder_path}"

        # Get Supabase client
        supabase = get_supabase_client()

        # List files from Supabase storage
        logger.info(f"Listing files from bucket '{bucket_name}' in path '{user_path}'")

        try:
            response = supabase.storage.from_(bucket_name).list(
                path=user_path,
                limit=limit,
                offset=0
            )

            # Check for listing errors
            if hasattr(response, 'error') and response.error:
                logger.error(f"Supabase listing error: {response.error}")
                return jsonify({
                    'error': f'Listing failed: {response.error}',
                    'success': False
                }), 500
        except Exception as list_error:
            logger.error(f"List exception: {list_error}")
            return jsonify({
                'error': f'Listing failed: {str(list_error)}',
                'success': False
            }), 500

        # Process the file list
        files = []
        file_list = getattr(response, 'data', []) if hasattr(response, 'data') else (response if isinstance(response, list) else [])

        for file_info in file_list:
            if file_info.get('name') and not file_info.get('name').endswith('/'):  # Skip directories
                file_path = f"{user_path}/{file_info['name']}"
                file_name = file_info['name']
                file_size = file_info.get('metadata', {}).get('size', 0)

                try:
                    public_url = supabase.storage.from_(bucket_name).get_public_url(file_path)
                except Exception:
                    public_url = f"https://rlkbxuuszlscnwagrsyx.supabase.co/storage/v1/object/public/{bucket_name}/{file_path}"

                # Get file extension and category
                extension = file_name.rsplit('.', 1)[1].lower() if '.' in file_name else ''
                category = get_file_category(file_name)

                files.append({
                    'name': file_name,
                    'path': file_path,
                    'publicUrl': public_url,
                    'extension': extension,
                    'category': category,
                    'size': file_size,
                    'sizeFormatted': format_file_size(file_size) if file_size else 'Unknown',
                    'contentType': file_info.get('metadata', {}).get('mimetype'),
                    'lastModified': file_info.get('updated_at'),
                    'created': file_info.get('created_at')
                })

        logger.info(f"Found {len(files)} files for user {user_id}")

        return jsonify({
            'success': True,
            'data': {
                'files': files,
                'count': len(files),
                'bucket': bucket_name,
                'path': user_path
            }
        }), 200

    except Exception as e:
        logger.error(f"Error listing images: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500

@image_upload_bp.route('/file-types', methods=['GET', 'OPTIONS'])
def get_supported_file_types():
    """
    Get information about supported file types.

    Returns:
        JSON response with supported file types and limits
    """
    # Handle OPTIONS request for CORS
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers['Access-Control-Allow-Origin'] = '*'
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Userid, userid, Authorization'
        return response

    try:
        # Prepare file type information
        file_types_info = {
            'success': True,
            'data': {
                'maxFileSize': MAX_FILE_SIZE,
                'maxFileSizeFormatted': format_file_size(MAX_FILE_SIZE),
                'defaultBucket': 'demo',
                'categories': {},
                'allExtensions': sorted(list(ALLOWED_EXTENSIONS))
            }
        }

        # Add category information
        for category, extensions in FILE_CATEGORIES.items():
            file_types_info['data']['categories'][category] = {
                'extensions': sorted(list(extensions)),
                'count': len(extensions),
                'description': get_category_description(category)
            }

        return jsonify(file_types_info), 200

    except Exception as e:
        logger.error(f"Error getting file types: {str(e)}", exc_info=True)
        return jsonify({
            'error': f'Internal server error: {str(e)}',
            'success': False
        }), 500

def get_category_description(category: str) -> str:
    """
    Get a description for a file category.

    Args:
        category: The file category

    Returns:
        Description string
    """
    descriptions = {
        'images': 'Image files including photos, graphics, and icons',
        'documents': 'Text documents and PDFs',
        'spreadsheets': 'Spreadsheet and data files',
        'presentations': 'Presentation files',
        'archives': 'Compressed archive files',
        'data': 'Structured data files (JSON, XML, YAML)'
    }
    return descriptions.get(category, f'{category.title()} files')