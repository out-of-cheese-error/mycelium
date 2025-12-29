"""
YouTube Transcript Service - Fetches transcripts from YouTube videos without API key.
Uses the youtube-transcript-api library for transcripts and youtube-search-python for search.
"""

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound, VideoUnavailable
from youtubesearchpython import VideosSearch
import re


class YouTubeTranscriptService:
    """Service to search YouTube and fetch transcripts from videos."""
    
    def search_videos(self, query: str, limit: int = 5) -> dict:
        """
        Search YouTube for videos matching a query.
        
        Args:
            query: Search query (title, topic, keywords)
            limit: Maximum number of results (default 5)
        
        Returns:
            Dict with list of video results
        """
        try:
            search = VideosSearch(query, limit=limit)
            results = search.result()
            
            videos = []
            for video in results.get('result', []):
                videos.append({
                    'title': video.get('title', 'Unknown'),
                    'video_id': video.get('id', ''),
                    'url': video.get('link', ''),
                    'duration': video.get('duration', 'Unknown'),
                    'channel': video.get('channel', {}).get('name', 'Unknown'),
                    'views': video.get('viewCount', {}).get('short', 'Unknown'),
                    'published': video.get('publishedTime', 'Unknown'),
                    'thumbnail': video.get('thumbnails', [{}])[0].get('url', '') if video.get('thumbnails') else ''
                })
            
            return {
                'success': True,
                'query': query,
                'count': len(videos),
                'videos': videos
            }
            
        except Exception as e:
            return {
                'success': False,
                'query': query,
                'error': f'Search failed: {str(e)}'
            }
    
    def format_search_results(self, result: dict) -> str:
        """Format search results as readable text."""
        if not result.get('success'):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        if not result.get('videos'):
            return f"No videos found for '{result.get('query')}'"
        
        output = [f"### YouTube Search: '{result['query']}' ({result['count']} results)\n"]
        
        for i, video in enumerate(result['videos'], 1):
            output.append(f"**{i}. {video['title']}**")
            output.append(f"   - Channel: {video['channel']}")
            output.append(f"   - Duration: {video['duration']} | Views: {video['views']}")
            output.append(f"   - URL: {video['url']}")
            output.append(f"   - Video ID: `{video['video_id']}`")
            output.append("")
        
        return "\n".join(output)
    
    def _extract_video_id(self, url_or_id: str) -> str:
        """
        Extract video ID from various YouTube URL formats or return as-is if already an ID.
        
        Supports:
        - https://www.youtube.com/watch?v=VIDEO_ID
        - https://youtu.be/VIDEO_ID
        - https://www.youtube.com/embed/VIDEO_ID
        - VIDEO_ID (raw)
        """
        # Already a video ID (11 characters, alphanumeric with - and _)
        if re.match(r'^[a-zA-Z0-9_-]{11}$', url_or_id):
            return url_or_id
        
        # Standard watch URL
        match = re.search(r'[?&]v=([a-zA-Z0-9_-]{11})', url_or_id)
        if match:
            return match.group(1)
        
        # Short URL (youtu.be)
        match = re.search(r'youtu\.be/([a-zA-Z0-9_-]{11})', url_or_id)
        if match:
            return match.group(1)
        
        # Embed URL
        match = re.search(r'youtube\.com/embed/([a-zA-Z0-9_-]{11})', url_or_id)
        if match:
            return match.group(1)
        
        # Return as-is and let the API handle the error
        return url_or_id
    
    def get_transcript(self, url_or_id: str, languages: list = None) -> dict:
        """
        Fetch transcript for a YouTube video.
        
        Args:
            url_or_id: YouTube URL or video ID
            languages: Optional list of language codes to prefer (e.g., ['en', 'de'])
        
        Returns:
            Dict with video_id, transcript text, segments, and metadata
        """
        video_id = self._extract_video_id(url_or_id)
        
        try:
            # New API: instantiate and use fetch() method
            api = YouTubeTranscriptApi()
            if languages:
                transcript = api.fetch(video_id, languages=languages)
            else:
                transcript = api.fetch(video_id)
            
            # Convert FetchedTranscript to list of segment dicts
            transcript_list = []
            for segment in transcript:
                transcript_list.append({
                    'text': segment.text,
                    'start': segment.start,
                    'duration': segment.duration
                })
            
            # Combine all segments into full text
            full_text = ' '.join([segment['text'] for segment in transcript_list])
            
            # Calculate total duration
            if transcript_list:
                last_segment = transcript_list[-1]
                total_duration = last_segment['start'] + last_segment.get('duration', 0)
            else:
                total_duration = 0
            
            return {
                'video_id': video_id,
                'success': True,
                'full_text': full_text,
                'segments': transcript_list,
                'segment_count': len(transcript_list),
                'total_duration_seconds': total_duration,
                'character_count': len(full_text)
            }
            
        except TranscriptsDisabled:
            return {
                'video_id': video_id,
                'success': False,
                'error': 'Transcripts are disabled for this video.'
            }
        except NoTranscriptFound:
            return {
                'video_id': video_id,
                'success': False,
                'error': 'No transcript found for this video. It may not have captions.'
            }
        except VideoUnavailable:
            return {
                'video_id': video_id,
                'success': False,
                'error': 'Video is unavailable or does not exist.'
            }
        except Exception as e:
            return {
                'video_id': video_id,
                'success': False,
                'error': f'Failed to fetch transcript: {str(e)}'
            }
    
    def list_available_transcripts(self, url_or_id: str) -> dict:
        """
        List all available transcripts for a video.
        
        Returns:
            Dict with available languages and types (manual vs auto-generated)
        """
        video_id = self._extract_video_id(url_or_id)
        
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            available = []
            for transcript in transcript_list:
                available.append({
                    'language': transcript.language,
                    'language_code': transcript.language_code,
                    'is_generated': transcript.is_generated,
                    'is_translatable': transcript.is_translatable
                })
            
            return {
                'video_id': video_id,
                'success': True,
                'transcripts': available
            }
            
        except Exception as e:
            return {
                'video_id': video_id,
                'success': False,
                'error': str(e)
            }
    
    def format_transcript(self, result: dict, include_timestamps: bool = False) -> str:
        """
        Format transcript result as readable text.
        
        Args:
            result: Result from get_transcript()
            include_timestamps: Whether to include timestamps for each segment
        
        Returns:
            Formatted transcript text
        """
        if not result.get('success'):
            return f"Error: {result.get('error', 'Unknown error')}"
        
        video_id = result['video_id']
        duration_mins = result['total_duration_seconds'] / 60
        
        header = f"YouTube Transcript (Video: {video_id})\n"
        header += f"Duration: {duration_mins:.1f} minutes | Segments: {result['segment_count']}\n"
        header += "-" * 50 + "\n\n"
        
        if include_timestamps:
            lines = []
            for segment in result['segments']:
                timestamp = self._format_timestamp(segment['start'])
                lines.append(f"[{timestamp}] {segment['text']}")
            content = '\n'.join(lines)
        else:
            content = result['full_text']
        
        return header + content
    
    def _format_timestamp(self, seconds: float) -> str:
        """Format seconds as MM:SS or HH:MM:SS."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes}:{secs:02d}"


    async def ingest_transcript(
        self,
        url_or_id: str,
        workspace_id: str,
        job_id: str,
        languages: list = None
    ) -> dict:
        """
        Ingest a YouTube transcript into the knowledge graph.
        
        Args:
            url_or_id: YouTube URL or video ID
            workspace_id: Workspace to ingest into
            job_id: Job ID for progress tracking
            languages: Optional preferred languages
        
        Returns:
            Dict with ingestion results
        """
        import os
        import uuid
        import time
        import asyncio
        from app.document_processor import process_file, ingest_status
        
        video_id = self._extract_video_id(url_or_id)
        
        # Initialize status dict for workspace if needed
        if workspace_id not in ingest_status:
            ingest_status[workspace_id] = {}
        
        # Update job status
        ingest_status[workspace_id][job_id] = {
            "status": "processing",
            "filename": f"youtube_{video_id}",
            "current": 0,
            "total": 100,
            "message": "Fetching transcript...",
            "type": "youtube",
            "updated_at": time.time()
        }
        
        # Fetch transcript - wrap sync call in thread to not block event loop
        try:
            result = await asyncio.to_thread(self.get_transcript, url_or_id, languages)
        except Exception as e:
            print(f"YouTube transcript fetch error: {e}")
            ingest_status[workspace_id][job_id] = {
                "status": "error",
                "message": f"Transcript fetch failed: {str(e)}",
                "updated_at": time.time()
            }
            return {'success': False, 'error': str(e)}
        
        if not result.get('success'):
            ingest_status[workspace_id][job_id] = {
                "status": "error",
                "message": result.get('error', 'Failed to fetch transcript'),
                "updated_at": time.time()
            }
            return result
        
        # Create temp file with transcript
        temp_dir = os.path.join(os.getcwd(), "temp", workspace_id)
        os.makedirs(temp_dir, exist_ok=True)
        
        filename = f"youtube_{video_id}_{uuid.uuid4().hex[:6]}.txt"
        file_path = os.path.join(temp_dir, filename)
        
        # Format with metadata header
        content = f"YouTube Video Transcript\n"
        content += f"Video ID: {video_id}\n"
        content += f"URL: https://youtube.com/watch?v={video_id}\n"
        content += f"Duration: {result['total_duration_seconds'] / 60:.1f} minutes\n"
        content += "-" * 50 + "\n\n"
        content += result['full_text']
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        ingest_status[workspace_id][job_id] = {
            "status": "processing",
            "message": "Processing transcript...",
            "current": 20,
            "total": 100,
            "filename": f"youtube_{video_id}",
            "type": "youtube",
            "updated_at": time.time()
        }
        
        # Process through document processor
        try:
            await process_file(file_path, workspace_id, chunk_size=4000, job_id=job_id)
            
            return {
                'success': True,
                'video_id': video_id,
                'character_count': result['character_count'],
                'duration_minutes': result['total_duration_seconds'] / 60
            }
        except Exception as e:
            print(f"YouTube ingestion error: {e}")
            ingest_status[workspace_id][job_id] = {
                "status": "error",
                "message": f"Ingestion failed: {str(e)}",
                "updated_at": time.time()
            }
            return {
                'success': False,
                'video_id': video_id,
                'error': str(e)
            }



# Global instance
youtube_service = YouTubeTranscriptService()
