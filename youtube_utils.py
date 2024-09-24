from urllib.parse import urlparse, parse_qs
import re
from langchain_community.document_loaders import YoutubeLoader
from youtube_transcript_api import YouTubeTranscriptApi
import youtube_utils

def convert_youtube_url(shared_url):
    # Parse the URL
    parsed_url = urlparse(shared_url)
    
    # Check if it's already a standard YouTube URL
    if parsed_url.netloc in ('www.youtube.com', 'youtube.com') and parsed_url.path == '/watch':
        return shared_url  # Return as is if it's already a standard URL
    
    # Extract video ID
    if parsed_url.netloc == 'youtu.be':
        video_id = parsed_url.path.lstrip('/')
    elif parsed_url.netloc in ('www.youtube.com', 'youtube.com'):
        video_id = parse_qs(parsed_url.query).get('v', [None])[0]
    else:
        raise ValueError("Invalid YouTube URL")
    
    if not video_id:
        raise ValueError("Could not extract video ID")
    
    # Construct the original URL
    original_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # Extract timestamp if present
    timestamp_match = re.search(r't=(\d+)', shared_url)
    if timestamp_match:
        timestamp = timestamp_match.group(1)
        original_url += f"&t={timestamp}s"
    
    return original_url

def get_youtube_transcript_api(url, languages=['ko', 'en']):
    video_id = url.split("v=")[1]
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        print(f"자막을 가져오는 데 실패했습니다: {str(e)}")
        return None
    
def get_youtube_transcript(url: str) -> str:
    url = convert_youtube_url(url)
    # Try to load the video content using the YoutubeLoader
    try:
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True, languages=['ko', 'en'])
        content = loader.load()
    # If the loader fails, try to get the transcript using the API
    except Exception as e:
        transcript = get_youtube_transcript_api(url)
        if transcript:
            content = transcript
        else:
            return None
    
    return content


def main():
    # Example usage
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    transcript = get_youtube_transcript(url)
    if transcript:
        print(transcript)
    else:
        print("Failed to retrieve transcript")

if __name__ == "__main__":
    main()