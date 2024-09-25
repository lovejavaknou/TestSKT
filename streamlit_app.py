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
from langchain_community.document_loaders import YoutubeLoader

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


def get_youtube_transcript_api(url, languages=['ko', 'en']):
    video_id = url.split("v=")[1]
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=languages)
        return " ".join([entry['text'] for entry in transcript])
    except Exception as e:
        print(f"자막을 가져오는 데 실패했습니다: {str(e)}")
        return None
    
def get_youtube_transcript(url: str) -> str:
    url = youtube_utils.convert_youtube_url(url)
    # Try to load the video content using the YoutubeLoader
    logger.debug(f"유튜브 URL: {url}")
    transcript = None
    try:
        loader = YoutubeLoader.from_youtube_url(url, add_video_info=True, language=['ko', 'en'])
        content = loader.load()
        if content:
            transcript = content[0].page_content
        logger.debug(f"로더를 통해 가져온 자막: {transcript}")
    # If the loader fails, try to get the transcript using the API
    except Exception as e:
        logger.debug(f"로더 실패: {str(e)}")
        transcript = get_youtube_transcript_api(url)
        logger.debug(f"API를 통해 가져온 자막: {transcript}")
    
    if not transcript:
        logger.warning("자막을 가져오는 데 실패했습니다. 다시 시도합니다.")
        transcript = get_youtube_transcript_api(url)
        logger.debug(f"재시도 후 가져온 자막: {transcript}")
    
    return transcript


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
claude_api_key = st.secrets["ANTHROPIC_API_KEY"]
youtube_api_key = st.secrets["YOUTUBE_API_KEY"]

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
        # 디버그 로그: 비디오 정보 가져오기 시도
        logger.debug(f"비디오 정보 가져오기 시도: {video_id}")
        
        # YouTube API 요청 생성: 비디오 ID에 해당하는 비디오의 snippet 정보를 요청
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        
        # API 요청 실행
        response = request.execute()
        
        # 응답에 'items' 키가 있고, 그 길이가 0보다 큰 경우 (즉, 비디오 정보를 성공적으로 가져온 경우)
        if 'items' in response and len(response['items']) > 0:
            # 비디오의 제목과 설명을 반환
            return response['items'][0]['snippet']['title'], response['items'][0]['snippet']['description']
        else:
            # 비디오 정보를 찾을 수 없는 경우 경고 로그와 사용자에게 오류 메시지 표시
            logger.warning(f"비디오 정보를 찾을 수 없습니다. 비디오 ID: {video_id}")
            st.error(f"비디오 정보를 찾을 수 없습니다. 비디오 ID: {video_id}")
            return None, None
    except Exception as e:
        # 예외 발생 시 예외 로그와 사용자에게 오류 메시지 표시
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
    # videos = []
    # next_page_token = None
    # start_date = datetime(2023, 1, 1).isoformat() + 'Z'
    # end_date = datetime(2024, 12, 31).isoformat() + 'Z'

    # while True:
    #     request = youtube.search().list(
    #         part="id,snippet",
    #         channelId=channel_id,
    #         maxResults=min(max_results, 50),
    #         order="date",
    #         type="video",
    #         publishedAfter=start_date,
    #         publishedBefore=end_date,
    #         pageToken=next_page_token
    #     )
    #     response = request.execute()
        
    #     for item in response['items']:
    #         video_id = item['id']['videoId']
    #         title = item['snippet']['title']
            
    #         # 조회수 가져오기
    #         video_response = youtube.videos().list(
    #             part='statistics',
    #             id=video_id
    #         ).execute()
            
    #         view_count = int(video_response['items'][0]['statistics']['viewCount'])
    #         videos.append((title, view_count))
        
    #     next_page_token = response.get('nextPageToken')
    #     if not next_page_token or len(videos) >= max_results:
    #         break

    videos = [('[날씨] 가을 햇살에 한낮엔 더워…큰 일교차 유의 / 연합뉴스TV (YonhapnewsTV)', 72), ('넷플릭스 &#39;흑백요리사&#39; 공개 첫 주 비영어권 1위 / 연합뉴스TV (YonhapnewsTV)', 29), ('[뉴스포커스] 윤 대통령-여 지도부 만찬…야, 재보선 신경전 가열 / 연합뉴스TV (YonhapnewsTV)', 67), ('&quot;인도 규제당국, 현대차 인도법인 IPO 승인&quot; / 연합뉴스TV (YonhapnewsTV)', 28), ('&#39;필리핀 이모&#39; 이탈에 대책 고심…주급제·통금시간 연장 / 연합뉴스TV (YonhapnewsTV)', 61), ('&#39;맥도날드 &#39;이중가격제&#39; 공지…&quot;배달 메뉴가 더 비싸&quot; / 연합뉴스TV (YonhapnewsTV)', 75), ('[뉴스포커스] 이스라엘, 헤즈볼라 &#39;융단폭격&#39;…레바논서 558명 사망 / 연합뉴스TV (YonhapnewsTV)', 869), ('마지막 유엔 연설 바이든 &quot;협력&quot;…트럼프 &quot;미국 우선&quot; / 연합뉴스TV (YonhapnewsTV)', 47), ('북한 오물 풍선에 인천·김포공항 올해 413분 운영 중단 / 연합뉴스TV (YonhapnewsTV)', 394), ('[날씨] 전국 흐리고 일교차 커…곳곳 약한 비 / 연합뉴스TV (YonhapnewsTV)', 428), ('[뉴스쏙] 폭염에 지각한 단풍…설악산 10월 하순에야 절정 | 이달 말까지는 낮에 30도…&#39;진짜 가을&#39;은 10월부터 / 연합뉴스TV (YonhapnewsTV)', 12011), ('&#39;집값 더 오른다&#39;…9월 주택가격전망지수 3년 만에 최고 / 연합뉴스TV (YonhapnewsTV)', 112), ('[뉴스쏙] 우크라 &quot;러 국경 돌파 두 번째 작전 성공&quot;vs러 &quot;돌파 시도 바로 격퇴…인접 지역에서 공격&quot;｜젤렌스키 &quot;전쟁 거의 끝나가&quot;…무기 사용제한 해제 요청', 59016), ('[뉴스쏙] &#39;홍명보논란&#39; 축구협회 현안질의 &#39;맨 오브 더 매치(MOM)&#39;박문성…&quot;정몽규 무능&quot;｜이임생 축구협회 이사, 국회 현안질의 도중 사퇴선언｜숱한논란속 홍명보·정몽규 직진선택', 32396), ('[핫클릭] &#39;세금 체납&#39; 박유천, 일본서 가수로 정식 데뷔 外 / 연합뉴스TV (YonhapnewsTV)', 136), ('[뉴스초점] 정몽규·홍명보 성토장 된 국회…&quot;계모임보다 못해&quot; / 연합뉴스TV (YonhapnewsTV)', 1468), ('[뉴스쏙] CNN &quot;해리스 48% vs 트럼프 47%&quot;…로이터도 해리스 우위 예상｜백임 남성 트럼프 확고한 지지…흑인·히스패닉, 해리스에 관심 / 연합뉴스TV', 4698), ('[뉴스쏙] 주미대사 &quot;북 도발 가능성, 한미 공조&quot;…바이든은 &#39;북한 패싱&#39;｜한미 &quot;북 심상치 않은 행보&quot;…중대 도발 전조 평가｜김여정, 한국 찾은 美 핵잠수함 위협 / 연합뉴스TV', 5344), ('[뉴스쏙] &#39;찐 가을&#39; 오려면 더 기다려야…9월말까지 낮 더위｜역대급 폭염에 단풍은 10월초부터…확 달라진 계절 / 연합뉴스TV (YonhapnewsTV)', 2062), ('&#39;핵 탑재 가능&#39; 러 폭격기, 북극해 등 비행 / 연합뉴스TV (YonhapnewsTV)', 303), ('젤렌스키 &quot;러, 북한·이란 전쟁범죄 공범 만들어&quot; / 연합뉴스TV (YonhapnewsTV)', 193), ('[이시각헤드라인] 9월 25일 라이브투데이2부 / 연합뉴스TV (YonhapnewsTV)', 236), ('[출근길 인터뷰] 남양주 광릉숲, &#39;1년에 한 번&#39; 비공개 숲길 개방 / 연합뉴스TV (YonhapnewsTV)', 173), ('[날씨] 아침 쌀쌀·한낮 포근 큰 일교차 유의…경남 약한 비 / 연합뉴스TV (YonhapnewsTV)', 808), ('[3분증시] 중국발 훈풍에 글로벌 증시 강세…코스피, 오름세 이어갈까 / 연합뉴스TV (YonhapnewsTV)', 153), ('&quot;해리스 48% vs 트럼프 47%&quot;…초박빙 계속 / 연합뉴스TV (YonhapnewsTV)', 528), ('검찰 수심위, 명품백 전달 &#39;최재영 기소&#39; 권고…8대7 의견 / 연합뉴스TV (YonhapnewsTV)', 209), ('박소연 전 케어 대표, 공무집행방해 징역형 집유 확정 / 연합뉴스TV (YonhapnewsTV)', 294), ('&quot;공천해 줄게&quot; 1억 가로챈 전 언론인 징역 2년 / 연합뉴스TV (YonhapnewsTV)', 148), ('&#39;나비박사&#39; 석주명 선생 곤충표본, 90년 만에 일본서 귀환 / 연합뉴스TV (YonhapnewsTV)', 159), ('전북 순창서 SUV가 오토바이 추돌…오토바이 운전자 사망 / 연합뉴스TV (YonhapnewsTV)', 257), ('한은의 경고…&quot;엔캐리 자금 2천억달러 청산 가능성&quot; / 연합뉴스TV (YonhapnewsTV)', 237), ('[날씨] 오늘도 일교차 큰 날씨 이어져…강한 너울 유의 / 연합뉴스TV (YonhapnewsTV)', 588), ('[사건사고] 고속도로 화물차 화재…타워팰리스 주차장서도 불 / 연합뉴스TV (YonhapnewsTV)', 403), ('[글로벌증시] 다우·S&amp;P500 또 사상 최고치…엔비디아, 120달러선 탈환 / 연합뉴스TV (YonhapnewsTV)', 180), ('추석 비상 주간 오늘까지…정부 &quot;응급의료 지원 연장&quot; / 연합뉴스TV (YonhapnewsTV)', 368), ('강원대 축제 흉기 난동 예고 20대 &quot;재미로 그랬다&quot; / 연합뉴스TV (YonhapnewsTV)', 312), ('소비자심리 두 달째 하락…집값 전망은 상승 / 연합뉴스TV (YonhapnewsTV)', 303), ('경부고속도로 서초IC서 버스 화재…인명피해 없어 / 연합뉴스TV (YonhapnewsTV)', 738), ('윤 대통령, 민단 간담회서 &quot;한일 우호 협력 관계 발전&quot; / 연합뉴스TV (YonhapnewsTV)', 177), ('[날씨클릭] 아침·저녁에는 쌀쌀해요…일교차 15도 안팎 / 연합뉴스TV (YonhapnewsTV)', 1194), ('[이 시각 핫뉴스] 부산 제과점 빵에서 500원 동전 크기 자석 나와 外 / 연합뉴스TV (YonhapnewsTV)', 398), ('&#39;최재영 수심위&#39; 청탁금지법 기소 권고…한 표 차로 엇갈려 / 연합뉴스TV (YonhapnewsTV)', 2791), ('&quot;민주, 호남 국민의힘&quot;…&quot;조국혁신당 사과·총장 해임&quot; / 연합뉴스TV (YonhapnewsTV)', 974), ('윤대통령·여 지도부, 90분 용산 만찬…한동훈, 독대 재요청 / 연합뉴스TV (YonhapnewsTV)', 3515), ('검찰 수심위, 명품백 전달 &#39;최재영 기소&#39; 권고…8대7 의견 / 연합뉴스TV (YonhapnewsTV)', 7128), ('[날씨] 큰 일교차 유의…내일 남해안·제주 중심 비 / 연합뉴스TV (YonhapnewsTV)', 938), ('[뉴스쏙] 이스라엘, 레바논에 24시간 동안 650차례 공습｜어린이·여성 등 최소 492명 사망·1,654명 부상｜유엔, &#39;수백 명 사망·긴장 고조&#39;에 강한 우려 표명', 5308), ('[뉴스쏙] 엎치락뒤치락 美 대선…경합주 승패 따라 승리 방정식 복잡｜해리스 캠프 &quot;트럼프는 여론조사보다 실제 선거에 강해&quot; 경계｜트럼프, 남부 경합주서 해리스에 2~5%p 우위달성', 4677), ('&#39;K-철도&#39; 글로벌 수출 속도…타지키스탄 진출하나 / 연합뉴스TV (YonhapnewsTV)', 1843)]

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

    # with st.sidebar:
    #     st.header("⚙️ 설정")
    #     global claude_api_key, youtube_api_key
    #     claude_api_key = st.text_input("Claude API 키", type="password", value=claude_api_key)
    #     youtube_api_key = st.text_input("YouTube API 키", type="password", value=youtube_api_key)
    #     st.caption("API 키는 안전하게 저장되며 세션이 종료되면 삭제됩니다.")
        
    #     if st.button("API 키 저장"):
    #         if claude_api_key and youtube_api_key:
    #             st.success("API 키가 저장되었습니다!")
    #         else:
    #             st.error("두 API 키를 모두 입력해주세요.")

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
                
                logger.info(f"YouTube URL: {youtube_url}")
                logger.info('convert_youtube_url: %s', youtube_utils.convert_youtube_url(youtube_url))

                
                transcript = youtube_utils.get_youtube_transcript(youtube_url)

                logger.info(f"transcript: {transcript}")


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
                
                logger.info(f"비디오 정보: 제목='{original_title}', 설명='{original_description}'")

                # 채널 영상 정보 가져오기
                status_text.text("채널 영상 정보를 분석하는 중...")
                progress_bar.progress(60)
                channel_id = "UCTHCOPwqNfZ0uiKOvFyhGwg"
                channel_videos = get_channel_videos(youtube, channel_id)

                logger.info(f"채널 영상 정보: {channel_videos}")

                # 요약 생성
                status_text.text("영상을 요약하는 중...")
                progress_bar.progress(80)
                summary = summarize_long_transcript(claude_client, transcript)
                if not summary:
                    st.error("영상 요약을 생성할 수 없습니다.")
                    return
                
                logger.info(f"요약 생성 완료: {summary}")

                # 콘텐츠 생성
                status_text.text("콘텐츠를 생성하는 중...")
                progress_bar.progress(90)
                content = generate_content(claude_client, summary, original_title, original_description, channel_videos)

                logger.info(f"콘텐츠 생성 완료: {content}")

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