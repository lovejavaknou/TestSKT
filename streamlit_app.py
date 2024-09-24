# 필요한 라이브러리 설치 (코드 실행 전 터미널에서 실행)
# pip install anthropic streamlit google-api-python-client youtube_transcript_api


from anthropic import Anthropic
import streamlit as st
import os
import time
import random
import logging
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs

# anthropic 라이브러리 임포트
try:
    import anthropic
except ImportError:
    st.error("anthropic 라이브러리가 설치되지 않았습니다. 터미널에서 'pip install anthropic'를 실행하여 설치해주세요.")
    st.stop()

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

# 여기에 youtube_utils 모듈이 있다고 가정합니다. 없다면 이 줄을 제거하거나 주석 처리하세요.
import youtube_utils

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# 나머지 코드는 그대로 유지...

# Streamlit 앱 설정
st.set_page_config(page_title="MZ외계인의 YouTube 콘텐츠 어시스턴트", layout="wide")

# 스타일 적용
st.markdown("""
<style>
.stButton>button {
    width: 100%;
}
.stTextInput>div>div>input {
    width: 100%;
}
@keyframes fall {
    0% { transform: translateY(-100%); opacity: 0; }
    10% { opacity: 1; }
    100% { transform: translateY(100vh); opacity: 1; }
}
.emoji {
    position: fixed;
    font-size: 72px;
    animation: fall linear infinite;
    z-index: 9999;
    top: -72px;
}
</style>
""", unsafe_allow_html=True)

# 이모티콘 애니메이션 추가
def add_emoji_animation():
    emojis = ["👽", "💗", "👻"]
    emoji_html = ""
    for i in range(20):  # 20개의 이모티콘 생성
        emoji = random.choice(emojis)
        left = random.uniform(0, 100)
        duration = random.uniform(5, 15)  # 애니메이션 지속 시간을 줄임
        delay = random.uniform(-5, 0)  # 시작 지연 시간을 음수로 설정하여 즉시 시작하게 함
        emoji_html += f"""
        <div class="emoji" style="left: {left}vw; animation-duration: {duration}s; animation-delay: {delay}s;">
            {emoji}
        </div>
        """
    return emoji_html

# 환경 변수에서 API 키 가져오기
claude_api_key = os.getenv("CLAUDE_API_KEY")
youtube_api_key = os.getenv("YOUTUBE_API_KEY")

def get_video_id(url):
    logger.debug(f"URL 파싱 시도: {url}")
    if "youtu.be" in url:
        return urlparse(url).path.strip("/")
    elif "youtube.com" in url:
        query = urlparse(url).query
        params = parse_qs(query)
        return params.get("v", [None])[0]
    else:
        logger.warning(f"유효하지 않은 YouTube URL: {url}")
        return None

def get_video_transcript(video_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.debug(f"자막 가져오기 시도 {attempt + 1}/{max_retries}: {video_id}")
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            logger.debug(f"사용 가능한 자막: {[tr.language_code for tr in transcript_list]}")
            
            for lang in ['ko', 'en']:
                try:
                    transcript = transcript_list.find_transcript([lang])
                    content = transcript.fetch()
                    logger.info(f"자막 가져오기 성공 (언어: {lang})")
                    return " ".join([entry['text'] for entry in content])
                except Exception as e:
                    logger.warning(f"{lang} 자막 가져오기 실패: {str(e)}")
            
            raise Exception("한국어와 영어 자막을 모두 찾을 수 없습니다.")
        except Exception as e:
            logger.exception(f"자막 가져오기 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(random.uniform(1, 3))
    return None

def get_captions_from_youtube_api(youtube, video_id, max_retries=3):
    for attempt in range(max_retries):
        try:
            logger.debug(f"YouTube API를 통한 자막 가져오기 시도 {attempt + 1}/{max_retries}")
            captions = youtube.captions().list(part="snippet", videoId=video_id).execute()
            
            logger.debug(f"사용 가능한 자막 트랙: {[item['snippet']['language'] for item in captions.get('items', [])]}")
            
            if not captions.get('items'):
                logger.warning("YouTube API: 자막 항목이 없습니다.")
                return None
            
            for lang in ['ko', 'en']:
                caption_id = next((item['id'] for item in captions['items'] if item['snippet']['language'] == lang), None)
                if caption_id:
                    subtitle = youtube.captions().download(id=caption_id, tfmt='srt').execute()
                    lines = subtitle.decode('utf-8').split('\n\n')
                    text_lines = [' '.join(line.split('\n')[2:]) for line in lines if len(line.split('\n')) > 2]
                    logger.info(f"YouTube API를 통해 {lang} 자막을 성공적으로 가져왔습니다.")
                    return ' '.join(text_lines)
            
            logger.warning("YouTube API: 한국어 또는 영어 자막을 찾을 수 없습니다.")
            return None
        except Exception as e:
            logger.exception(f"YouTube API를 통한 자막 가져오기 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            time.sleep(random.uniform(1, 3))
    return None

def get_video_details(youtube, video_id):
    try:
        logger.debug(f"비디오 정보 가져오기 시도: {video_id}")
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()
        if 'items' in response and len(response['items']) > 0:
            return response['items'][0]['snippet']['title'], response['items'][0]['snippet']['description']
        else:
            logger.warning(f"비디오 정보를 찾을 수 없습니다. 비디오 ID: {video_id}")
            st.error(f"비디오 정보를 찾을 수 없습니다. 비디오 ID: {video_id}")
            return None, None
    except Exception as e:
        logger.exception(f"영상 정보를 가져오는 데 실패: {str(e)}")
        st.error(f"영상 정보를 가져오는 데 실패했습니다: {str(e)}")
        return None, None

def check_captions(youtube, video_id):
    try:
        captions = youtube.captions().list(
            part="snippet",
            videoId=video_id
        ).execute()
        
        available_captions = []
        for item in captions.get("items", []):
            available_captions.append(f"{item['snippet']['language']} ({item['snippet']['trackKind']})")
        
        if available_captions:
            st.info(f"사용 가능한 자막 트랙: {', '.join(available_captions)}")
        else:
            st.warning("YouTube API를 통해 확인한 결과, 이 동영상에는 사용 가능한 자막이 없습니다.")
        
        return captions
    except Exception as e:
        st.error(f"자막 정보를 가져오는 데 실패했습니다: {str(e)}")
        return None

def chunk_transcript(transcript, chunk_size=3000):
    words = transcript.split()
    chunks = []
    current_chunk = []
    current_length = 0
    for word in words:
        if current_length + len(word) > chunk_size:
            chunks.append(" ".join(current_chunk))
            current_chunk = [word]
            current_length = len(word)
        else:
            current_chunk.append(word)
            current_length += len(word) + 1  # +1 for space
    if current_chunk:
        chunks.append(" ".join(current_chunk))
    return chunks

from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT

def generate_content_safely(client, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            time.sleep(2)  # API 호출 사이에 2초 대기
            message = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0.7,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            logger.debug(f"API Response: {message}")
            return message.content[0].text
        except Exception as e:
            logger.exception(f"Anthropic API 오류 (시도 {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                logger.warning(f"재시도 중... (시도 {attempt + 1}/{max_retries})")
                st.warning(f"재시도 중... (시도 {attempt + 1}/{max_retries})")
                time.sleep(5)  # 오류 발생 시 5초 대기 후 재시도
            else:
                logger.error(f"콘텐츠 생성 중 오류 발생: {str(e)}")
                st.error(f"콘텐츠 생성 중 오류 발생: {str(e)}")
                return None
    return None

def summarize_long_transcript(client, transcript):
    chunks = chunk_transcript(transcript)
    summaries = []
    for chunk in chunks:
        summary_prompt = f"다음 텍스트를 1-2문장으로 요약해주세요:\n\n{chunk[:1000]}"
        summary = generate_content_safely(client, summary_prompt)
        if summary:
            summaries.append(summary)
    
    if summaries:
        final_summary_prompt = f"다음은 긴 영상의 부분 요약들입니다. 이를 바탕으로 전체 내용을 3줄로 요약해주세요:\n\n{' '.join(summaries)[:2000]}"
        final_summary = generate_content_safely(client, final_summary_prompt)
        return final_summary
    return None

def get_channel_videos(youtube, channel_id, max_results=50):
    videos = []
    next_page_token = None
    start_date = datetime(2023, 1, 1).isoformat() + 'Z'
    end_date = datetime(2024, 12, 31).isoformat() + 'Z'

    while True:
        request = youtube.search().list(
            part="id,snippet",
            channelId=channel_id,
            maxResults=min(max_results, 50),
            order="date",
            type="video",
            publishedAfter=start_date,
            publishedBefore=end_date,
            pageToken=next_page_token
        )
        response = request.execute()
        
        for item in response['items']:
            video_id = item['id']['videoId']
            title = item['snippet']['title']
            
            # 조회수 가져오기
            video_response = youtube.videos().list(
                part='statistics',
                id=video_id
            ).execute()
            
            view_count = int(video_response['items'][0]['statistics']['viewCount'])
            videos.append((title, view_count))
        
        next_page_token = response.get('nextPageToken')
        if not next_page_token or len(videos) >= max_results:
            break

    return videos

def generate_content(client, summary, original_title, original_description, channel_videos):
    # 채널 영상 정보 정리
    top_videos = sorted(channel_videos, key=lambda x: x[1], reverse=True)[:10]
    video_info = "\n".join([f"- {title} (조회수: {views:,})" for title, views in top_videos])

    # 요약 생성
    summary_prompt = f"다음 YouTube 영상 요약을 5개의 주요 포인트로 나누어 설명해주세요. 각 포인트는 하나의 문장으로 작성하고, 적절한 이모지를 문장 시작에 추가해주세요. 번호는 붙이지 마세요:\n\n{summary}"
    summary_result = generate_content_safely(client, summary_prompt)

    # 타이틀 생성
    categories = ["흥미유발", "정보성", "문제제기", "드라마틱", "전문성"]
    titles = []
    for category in categories:
        title_prompt = f"다음 YouTube 영상 요약을 바탕으로 '{category}' 카테고리에 맞는 매력적인 제목을 1개 생성해주세요:\n" \
                       f"- 마크다운 형식(#, *, 등)을 사용하지 마세요.\n" \
                       f"- 적절한 이모지를 사용하세요.\n" \
                       f"- 제목은 한 문장으로 작성하세요.\n" \
                       f"- '{category}'라는 단어를 제목에 포함시키지 마세요.\n" \
                       f"- 다음은 우리 채널의 인기 있는 영상 제목과 조회수입니다. 이를 참고하여 비슷한 스타일로 제목을 생성해주세요:\n" \
                       f"{video_info}\n\n" \
                       f"원래 제목: '{original_title}'\n\n{summary}"
        title = generate_content_safely(client, title_prompt)
        titles.append(title.strip() if title else f"({category} 제안 없음)")

    # 밈을 활용한 제목 생성
    meme_title_prompt = f"다음 YouTube 영상 요약을 바탕으로 최근 유행하는 인터넷 밈이나 유행어를 활용한 매력적인 제목을 3개 생성해주세요:\n" \
                        f"- 각 제목은 반드시 밈이나 유행어를 포함해야 합니다.\n" \
                        f"- 제목 뒤에 괄호로 사용한 밈이나 유행어를 명시해주세요. 예: '제목 (활용 밈: 밈 이름)'\n" \
                        f"- 마크다운 형식(#, *, 등)을 사용하지 마세요.\n" \
                        f"- 적절한 이모지를 사용하세요.\n" \
                        f"- 각 제목은 새로운 줄에 작성하고, 번호를 붙이지 마세요.\n" \
                        f"- 다음은 우리 채널의 인기 있는 영상 제목과 조회수입니다. 이를 참고하여 비슷한 스타일로 제목을 생성해주세요:\n" \
                        f"{video_info}\n\n{summary}"
    meme_titles = generate_content_safely(client, meme_title_prompt)
    if meme_titles:
        meme_titles = [title.strip() for title in meme_titles.split('\n') if title.strip()]
    titles.extend(meme_titles[:3])  # 최대 3개의 밈 제목만 사용

    # 8개의 제목을 보장
    while len(titles) < 8:
        titles.append("(제안 없음)")

    # 설명 생성
    description_prompt = f"다음 YouTube 영상 요약을 바탕으로 2개의 흥미로운 설명을 생성해주세요. 각 설명에 적절한 이모지를 섞어 친절하고 귀엽게, 센스있게 구성해주세요. 번호는 붙이지 마세요. 원래 설명 참고: '{original_description[:200]}'\n\n{summary}"
    descriptions = generate_content_safely(client, description_prompt)

    # 해시태그 생성
    hashtag_prompt = f"다음 YouTube 영상 요약을 바탕으로 관련 해시태그를 생성해주세요.\n" \
                     f"다음 4개의 해시태그는 반드시 포함되어야 합니다: #SK텔레콤 #SKtelecom #SKT #AI\n" \
                     f"이 4개를 제외하고 추가로 10개의 관련 해시태그를 생성해주세요.\n" \
                     f"각 해시태그는 '#'로 시작하고 띄어쓰기 없이 작성해주세요.\n" \
                     f"총 14개의 해시태그가 되어야 합니다:\n\n{summary}"
    hashtags = generate_content_safely(client, hashtag_prompt)

    # 퀴즈 생성
    def generate_quizzes(max_attempts=3):
        for attempt in range(max_attempts):
            quiz_prompt = f"다음 YouTube 영상 요약을 바탕으로 시청자가 참여할 수 있는 3개의 간단한 퀴즈 문제를 만들어주세요. 각 문제는 다음 형식을 정확히 따라주세요:\n\n" \
                          f"질문: (질문 내용)\n" \
                          f"a) 정답\n" \
                          f"b) 오답1\n" \
                          f"c) 오답2\n\n" \
                          f"반드시 3개의 퀴즈를 생성해야 하며, 각 퀴즈는 질문과 3개의 선택지를 포함해야 합니다. 퀴즈 사이에는 빈 줄을 넣어주세요.\n\n{summary}"
            quizzes = generate_content_safely(client, quiz_prompt)

            parsed_quizzes = []
            if quizzes:
                quiz_list = quizzes.split('\n\n')
                for quiz in quiz_list:
                    lines = quiz.split('\n')
                    if len(lines) >= 4 and lines[0].startswith("질문:"):
                        parsed_quizzes.append({
                            "question": lines[0].split(":", 1)[1].strip(),
                            "options": [line.strip() for line in lines[1:4]]
                        })

            if len(parsed_quizzes) == 3:
                return parsed_quizzes

        # 모든 시도 후에도 실패한 경우
        return [{"question": "퀴즈를 생성할 수 없습니다.", "options": ["N/A", "N/A", "N/A"]} for _ in range(3)]

    quizzes = generate_quizzes()

    # 결과를 딕셔너리 형태로 반환
    return {
        "요약": summary_result,
        "타이틀 제안": titles,
        "디스크립션": descriptions,
        "해시태그": hashtags,
        "콘텐츠 피드백 (퀴즈)": quizzes
    }

def display_results(content):
    # 요약
    st.header("📌 요약")
    summary_points = [point.strip() for point in content["요약"].split("\n") if point.strip()]
    for i, point in enumerate(summary_points[:5], 1):
        st.markdown(f"**{i}. {point}**")

    # 타이틀 제안
    st.header("🏷️ 타이틀 제안")
    titles = content["타이틀 제안"]
    categories = ["흥미유발", "정보성", "문제제기", "드라마틱", "전문성"]
    for i, title in enumerate(titles[:8], 1):
        if i <= 5:
            st.markdown(f"**{i}. {categories[i-1]}: {title}**")
        else:
            if "(" in title and ")" in title:
                title_text, meme = title.rsplit("(", 1)
                st.markdown(f"**{i}. {title_text.strip()}** ({meme.strip()})")
            else:
                st.markdown(f"**{i}. {title}** (활용 밈: 없음)")

    # 디스크립션
    st.header("📝 디스크립션")
    descriptions = [desc.strip() for desc in content["디스크립션"].split("\n") if desc.strip()]
    for i, desc in enumerate(descriptions[:2], 1):
        st.markdown(f"{i}. {desc}")

    # 해시태그
    st.header("🔗 해시태그")
    hashtags = content["해시태그"].split()
    st.markdown(" ".join([f"`{tag}`" for tag in hashtags]))

    # 퀴즈
    st.header("❓ 콘텐츠 피드백 (퀴즈)")
    quizzes = content["콘텐츠 피드백 (퀴즈)"]
    for i, quiz in enumerate(quizzes, 1):
        st.markdown(f"**퀴즈 {i}**")
        st.markdown(f"**{quiz['question']}**")
        if quiz['options'][0] != "N/A":
            for option in quiz['options']:
                st.markdown(f"- {option}")
        else:
            st.markdown("퀴즈 생성에 실패했습니다.")
        st.markdown("")  # 퀴즈 간 공백 추가

def main():
    st.title("👽MZ외계인👽이 도와주는 YouTube 영상 발행 준비")
    st.markdown("""
    YouTube 영상 URL을 입력하면 AI가 자동으로 요약, 타이틀 제안, 설명 생성, 해시태그 추천, 그리고 퀴즈까지 만들어드립니다!
    """)

    emoji_placeholder = st.empty()

    with st.sidebar:
        st.header("⚙️ 설정")
        global claude_api_key, youtube_api_key
        claude_api_key = st.text_input("Claude API 키", type="password", value=claude_api_key)
        youtube_api_key = st.text_input("YouTube API 키", type="password", value=youtube_api_key)
        st.caption("API 키는 안전하게 저장되며 세션이 종료되면 삭제됩니다.")
        
        if st.button("API 키 저장"):
            if claude_api_key and youtube_api_key:
                st.success("API 키가 저장되었습니다!")
            else:
                st.error("두 API 키를 모두 입력해주세요.")

    if not claude_api_key or not youtube_api_key:
        st.warning("사이드바에 Claude API 키와 YouTube API 키를 입력해주세요.")
        emoji_placeholder.markdown(add_emoji_animation(), unsafe_allow_html=True)
        return

    try:
        claude_client = Anthropic(api_key=claude_api_key)
        youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    except Exception as e:
        st.error(f"API 설정 중 오류가 발생했습니다: {str(e)}")
        return

    st.header("📺 영상 정보 입력")
    youtube_url = st.text_input("YouTube 영상 URL을 입력하세요:", placeholder="https://www.youtube.com/watch?v=...")

    if not youtube_url:
        emoji_placeholder.markdown(add_emoji_animation(), unsafe_allow_html=True)

    if st.button("✨요약, 타이틀, 디스크립션, 해시태그, 퀴즈 부탁해요🙏", key="generate_content_button"):
        emoji_placeholder.empty()
        if youtube_url:
            video_id = get_video_id(youtube_url)
            if not video_id:
                st.error("올바른 YouTube URL을 입력해주세요.")
                return

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                # 트랜스크립트 가져오기
                status_text.text("자막을 가져오는 중...")
                progress_bar.progress(20)
                
                transcript = youtube_utils.get_youtube_transcript(youtube_url)

                if transcript is None:
                    logger.warning("YouTubeTranscriptApi를 통한 자막 가져오기 실패. YouTube Data API를 통해 시도합니다.")
                    transcript = get_captions_from_youtube_api(youtube, video_id)
                
                if transcript is None:
                    st.error("모든 방법으로 자막을 가져오는 데 실패했습니다. 요약을 진행할 수 없습니다.")
                    logger.error("자막 가져오기 실패 - 모든 방법 시도 후 실패")
                    return
                
                if len(transcript.strip()) < 10:
                    st.error("가져온 자막이 너무 짧아 유효하지 않습니다. 요약을 진행할 수 없습니다.")
                    logger.error(f"가져온 자막이 너무 짧습니다: '{transcript}'")
                    return
                
                logger.info(f"성공적으로 자막을 가져왔습니다. 자막 길이: {len(transcript)} 문자")
                st.success(f"자막을 성공적으로 가져왔습니다. (길이: {len(transcript)} 문자)")

                # 비디오 정보 가져오기
                status_text.text("영상 정보를 가져오는 중...")
                progress_bar.progress(40)
                original_title, original_description = get_video_details(youtube, video_id)
                if original_title is None or original_description is None:
                    return

                # 채널 영상 정보 가져오기
                status_text.text("채널 영상 정보를 분석하는 중...")
                progress_bar.progress(60)
                channel_id = "UCTHCOPwqNfZ0uiKOvFyhGwg"
                channel_videos = get_channel_videos(youtube, channel_id)

                # 요약 생성
                status_text.text("영상을 요약하는 중...")
                progress_bar.progress(80)
                summary = summarize_long_transcript(claude_client, transcript)
                if not summary:
                    st.error("영상 요약을 생성할 수 없습니다.")
                    return

                # 콘텐츠 생성
                status_text.text("콘텐츠를 생성하는 중...")
                progress_bar.progress(90)
                content = generate_content(claude_client, summary, original_title, original_description, channel_videos)

                # 결과 표시
                progress_bar.progress(100)
                status_text.text("완료!")
                st.success("콘텐츠 생성이 완료되었습니다!")

                # 결과 섹션
                display_results(content)

            except Exception as e:
                st.error(f"콘텐츠 생성 중 오류가 발생했습니다: {str(e)}")
            finally:
                progress_bar.empty()
                status_text.empty()
        else:
            st.warning("YouTube URL을 입력해주세요.")
            emoji_placeholder.markdown(add_emoji_animation(), unsafe_allow_html=True)

if __name__ == "__main__":
    main()