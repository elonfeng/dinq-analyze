import os
import json
import logging
import requests
from datetime import datetime
from typing import Any, Optional, Dict, List

# Try to use DINQ project's trace logging system
try:
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from utils.trace_context import get_trace_logger
    logger = get_trace_logger(__name__)
except ImportError:
    # If cannot import, use standard logging
    logger = logging.getLogger(__name__)

# YouTube分析器不使用缓存功能

class YouTubeAnalyzer:
    """YouTube Channel Analyzer - 参考LinkedInAnalyzer设计"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.youtube_api_key = config.get("youtube", {}).get("api_key", "")

        # YouTube API base URL
        self.youtube_api_base = "https://www.googleapis.com/youtube/v3"

        logger.info("YouTube analyzer initialized successfully")

    def get_result_with_progress(self, channel_input: str, progress_callback, youtube_url: str = None):
        """
        带进度回调的分析方法 - 参考LinkedIn的get_result_with_progress
        """
        try:
            # 1. 解析频道ID
            progress_callback('parsing_input', 'Parsing channel input...')
            channel_id = self._parse_channel_input(channel_input, youtube_url)
            
            if not channel_id:
                logger.error(f"Could not parse channel ID from input: {channel_input}")
                return None
            
            # 2. 获取频道数据
            progress_callback('fetching_channel', 'Fetching channel data...')
            
            # 3. 获取频道基础信息
            progress_callback('fetching_channel', 'Fetching channel information...')
            channel_data = self._get_channel_info(channel_id)
            
            if not channel_data:
                logger.error(f"Could not fetch channel data for ID: {channel_id}")
                return None
            
            # 4. 获取代表性视频
            progress_callback('fetching_video', 'Finding representative video...')
            representative_video = self._get_representative_video(channel_id)

            # 5. 获取内容分析数据
            progress_callback('analyzing_content', 'Analyzing content types...')
            content_summary = self._analyze_content_types(channel_id)

            # 6. 组装分析结果
            progress_callback('generating_result', 'Generating analysis result...')
            result = self._build_analysis_result(channel_data, representative_video, content_summary)
            

            
            progress_callback('completed', 'Analysis completed')
            return result
            
        except Exception as e:
            logger.error(f"Error in YouTube analysis: {e}")
            return None

    def get_result(self, channel_input: str, youtube_url: str = None):
        """
        同步分析方法 - 参考LinkedIn的get_result
        """
        return self.get_result_with_progress(channel_input, lambda *args: None, youtube_url)



    def _parse_channel_input(self, channel_input: str, youtube_url: str = None) -> Optional[str]:
        """
        解析各种输入格式获取频道ID
        支持：频道ID、频道URL、频道名称
        """
        try:
            # 如果提供了youtube_url，优先使用
            if youtube_url:
                channel_input = youtube_url
            
            # 如果是完整的YouTube URL
            if 'youtube.com/channel/' in channel_input:
                # 提取频道ID：https://www.youtube.com/channel/UCxxxxxx
                return channel_input.split('youtube.com/channel/')[1].split('?')[0].split('/')[0]
            elif 'youtube.com/c/' in channel_input:
                # 自定义URL：https://www.youtube.com/c/channelname
                custom_name = channel_input.split('youtube.com/c/')[1].split('?')[0].split('/')[0]
                return self._get_channel_id_by_custom_url(custom_name)
            elif 'youtube.com/@' in channel_input:
                # 新格式：https://www.youtube.com/@channelname
                handle = channel_input.split('youtube.com/@')[1].split('?')[0].split('/')[0]
                return self._get_channel_id_by_handle(handle)
            elif channel_input.startswith('UC') and len(channel_input) == 24:
                # 直接是频道ID
                return channel_input
            else:
                # 尝试作为频道名称搜索
                return self._search_channel_by_name(channel_input)
                
        except Exception as e:
            logger.error(f"Error parsing channel input: {e}")
            return None

    def _get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        获取频道基础信息
        """
        try:
            url = f"{self.youtube_api_base}/channels"
            params = {
                'part': 'snippet,statistics,brandingSettings',
                'id': channel_id,
                'key': self.youtube_api_key
            }
            
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                return data['items'][0]
            else:
                logger.warning(f"No channel found for ID: {channel_id}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting channel info: {e}")
            return None

    def _get_representative_video(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """
        获取代表性视频 - 直接在核心逻辑中处理
        """
        try:
            logger.info(f"Getting representative video for channel: {channel_id}")

            # 检查API密钥
            if not self.youtube_api_key:
                logger.error("YouTube API key is not configured")
                return None

            # 先尝试获取频道的播放列表，然后获取视频
            # 使用channels API获取上传播放列表ID
            channels_url = f"{self.youtube_api_base}/channels"
            channels_params = {
                'part': 'contentDetails',
                'id': channel_id,
                'key': self.youtube_api_key
            }

            logger.info(f"Getting channel details from: {channels_url}")
            channels_response = requests.get(channels_url, params=channels_params)
            channels_response.raise_for_status()
            channels_data = channels_response.json()

            logger.info(f"Channels API response: {channels_data}")

            if not channels_data.get('items'):
                logger.warning("No channel data found")
                return None

            # 获取上传播放列表ID
            uploads_playlist_id = channels_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']
            logger.info(f"Uploads playlist ID: {uploads_playlist_id}")

            # 获取播放列表中的视频
            playlist_url = f"{self.youtube_api_base}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': uploads_playlist_id,
                'maxResults': 1,
                'key': self.youtube_api_key
            }

            logger.info(f"Making YouTube API request to: {playlist_url}")
            response = requests.get(playlist_url, params=params)
            response.raise_for_status()
            data = response.json()

            logger.info(f"YouTube API response: {data}")

            if data.get('items'):
                video = data['items'][0]
                # 播放列表API中视频ID在resourceId.videoId
                video_id = video['snippet']['resourceId']['videoId']

                result = {
                    'video_id': video_id,
                    'title': video['snippet']['title'],
                    'thumbnail': video['snippet']['thumbnails']['high']['url'],
                    'embed_code': f'<iframe width="560" height="315" src="https://www.youtube.com/embed/{video_id}" frameborder="0" allowfullscreen></iframe>'
                }
                logger.info(f"Found representative video: {result}")
                return result
            else:
                logger.warning("No videos found in YouTube API response")

            return None

        except Exception as e:
            logger.error(f"Error getting representative video: {e}")
            return None

    def _analyze_content_types(self, channel_id: str) -> str:
        """
        分析频道内容类型，生成AI摘要
        """
        try:
            logger.info(f"Analyzing content types for channel: {channel_id}")

            # 第一步：获取最新2个视频
            latest_videos = self._search_videos(channel_id, order='date', max_results=2)
            logger.info(f"Found {len(latest_videos)} latest videos")

            # 第二步：获取最热门3个视频
            popular_videos = self._search_videos(channel_id, order='viewCount', max_results=3)
            logger.info(f"Found {len(popular_videos)} popular videos")

            # 第三步：合并视频ID并去重
            all_video_ids = []
            seen_ids = set()

            for video in latest_videos + popular_videos:
                video_id = video['id']['videoId'] if 'id' in video and 'videoId' in video['id'] else video.get('id')
                if video_id and video_id not in seen_ids:
                    all_video_ids.append(video_id)
                    seen_ids.add(video_id)

            logger.info(f"Total unique video IDs: {len(all_video_ids)}")

            if not all_video_ids:
                logger.warning("No video IDs found, returning default summary")
                return "Diverse Content Creator"

            # 第四步：获取视频详细信息
            videos_details = self._get_video_details(all_video_ids)
            logger.info(f"Got details for {len(videos_details)} videos")

            # 第五步：使用AI生成内容摘要
            content_summary = self._generate_content_summary(videos_details)
            logger.info(f"Generated content summary: {content_summary}")

            return content_summary or "Diverse Content Creator"

        except Exception as e:
            logger.error(f"Error analyzing content types: {e}")
            return "Diverse Content Creator"

    def _search_videos(self, channel_id: str, order: str = 'date', max_results: int = 2) -> List[Dict]:
        """
        搜索频道视频 - 使用播放列表方式
        """
        try:
            # 先获取频道的上传播放列表ID
            channels_url = f"{self.youtube_api_base}/channels"
            channels_params = {
                'part': 'contentDetails',
                'id': channel_id,
                'key': self.youtube_api_key
            }

            channels_response = requests.get(channels_url, params=channels_params)
            channels_response.raise_for_status()
            channels_data = channels_response.json()

            if not channels_data.get('items'):
                logger.warning(f"No channel data found for {channel_id}")
                return []

            # 获取上传播放列表ID
            uploads_playlist_id = channels_data['items'][0]['contentDetails']['relatedPlaylists']['uploads']

            # 获取播放列表中的视频
            playlist_url = f"{self.youtube_api_base}/playlistItems"
            params = {
                'part': 'snippet',
                'playlistId': uploads_playlist_id,
                'maxResults': max_results,
                'key': self.youtube_api_key
            }

            response = requests.get(playlist_url, params=params)
            response.raise_for_status()
            data = response.json()

            # 转换格式以匹配原来的search API格式
            items = []
            for item in data.get('items', []):
                items.append({
                    'id': {'videoId': item['snippet']['resourceId']['videoId']},
                    'snippet': item['snippet']
                })

            return items

        except Exception as e:
            logger.error(f"Error searching videos: {e}")
            return []

    def _get_video_details(self, video_ids: List[str]) -> List[Dict]:
        """
        获取视频详细信息
        """
        try:
            if not video_ids:
                return []

            videos_url = f"{self.youtube_api_base}/videos"
            params = {
                'part': 'snippet,statistics',
                'id': ','.join(video_ids),
                'key': self.youtube_api_key
            }

            response = requests.get(videos_url, params=params)
            response.raise_for_status()
            data = response.json()

            return data.get('items', [])

        except Exception as e:
            logger.error(f"Error getting video details: {e}")
            return []

    def _generate_content_summary(self, videos_data: List[Dict]) -> str:
        """
        使用AI生成内容类型摘要
        """
        try:
            if not videos_data:
                return None

            # 提取视频文本内容
            content_texts = []
            for video in videos_data:
                snippet = video.get('snippet', {})
                text = f"标题: {snippet.get('title', '')}\n"

                # 限制描述长度
                description = snippet.get('description', '')
                if description:
                    text += f"描述: {description[:200]}...\n"

                # 添加标签（如果有）
                tags = snippet.get('tags', [])
                if tags:
                    text += f"标签: {', '.join(tags[:5])}\n"

                content_texts.append(text)

            # 构建AI提示词
            prompt = f"""
Based on the following YouTube video data, generate a 60-70 character summary describing the channel's content types:

Video data:
{chr(10).join(content_texts)}

Requirements:
1. Summary length must be strictly 60-70 characters
2. Highlight the channel's core content features
3. Use concise and accurate descriptions
4. Avoid redundant words like "this channel"
5. Directly describe content types, e.g., "Gaming tutorials, reviews, and entertainment content"
6. Use English only

Summary:"""

            # 复用LinkedIn分析器的AI服务
            summary = self._call_ai_service(prompt)

            # 长度控制逻辑（保险机制，防止LLM生成过长内容）
            if summary and len(summary) > 90:
                summary = summary[:87] + "..."

            return summary

        except Exception as e:
            logger.error(f"Error generating content summary: {e}")
            return None

    def _call_ai_service(self, prompt: str) -> str:
        """
        复用LinkedIn分析器的AI服务
        """
        try:
            # 导入LinkedIn分析器
            from linkedin_analyzer.analyzer import LinkedInAnalyzer

            # 创建LinkedIn分析器实例（复用配置）
            linkedin_config = {
                "use_cache": False,  # 不使用缓存
                "ai_service": "kimi"  # 使用相同的AI服务
            }
            linkedin_analyzer = LinkedInAnalyzer(linkedin_config)

            # 调用Kimi API服务
            response = linkedin_analyzer._call_kimi_api(prompt)

            return response.strip() if response else None

        except Exception as e:
            logger.error(f"Error calling AI service: {e}")
            return None

    def _build_analysis_result(self, channel_data: Dict, representative_video: Dict, content_summary: str = None) -> Dict[str, Any]:
        """
        构建分析结果 - 包含内容摘要
        """
        try:
            statistics = channel_data.get('statistics', {})
            snippet = channel_data.get('snippet', {})

            result = {
                'channel_name': snippet.get('title', ''),
                'channel_url': f"https://www.youtube.com/channel/{channel_data.get('id', '')}",
                'subscriber_count': int(statistics.get('subscriberCount', 0)),
                'total_view_count': int(statistics.get('viewCount', 0)),
                'video_count': int(statistics.get('videoCount', 0)),
                'representative_video': representative_video,
                'analysis_date': datetime.now().isoformat(),
                'channel_id': channel_data.get('id', '')
            }

            # 添加内容摘要（如果有）
            if content_summary:
                result['content_summary'] = content_summary

            return result

        except Exception as e:
            logger.error(f"Error building analysis result: {e}")
            return None



    def _search_channel_by_name(self, channel_name: str) -> Optional[str]:
        """
        通过频道名称搜索获取频道ID
        """
        try:
            search_url = f"{self.youtube_api_base}/search"
            params = {
                'part': 'snippet',
                'q': channel_name,
                'type': 'channel',
                'maxResults': 1,
                'key': self.youtube_api_key
            }
            
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get('items'):
                return data['items'][0]['id']['channelId']
            
            return None
            
        except Exception as e:
            logger.error(f"Error searching channel by name: {e}")
            return None

    def _get_channel_id_by_custom_url(self, custom_name: str) -> Optional[str]:
        """
        通过自定义URL获取频道ID
        """
        # YouTube API v3 不直接支持通过自定义URL获取频道ID
        # 这里使用搜索作为fallback
        return self._search_channel_by_name(custom_name)

    def _get_channel_id_by_handle(self, handle: str) -> Optional[str]:
        """
        通过@handle获取频道ID
        """
        # YouTube API v3 不直接支持通过handle获取频道ID
        # 这里使用搜索作为fallback
        return self._search_channel_by_name(handle)
