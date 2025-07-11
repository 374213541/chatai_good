import os
import sys
import streamlit as st
from datetime import datetime
import base64
import requests
from openai import OpenAI
import streamlit.components.v1 as components
import time
import websocket
import hashlib
import hmac
import json
import ssl
from urllib.parse import urlencode
from time import mktime
from wsgiref.handlers import format_date_time
import threading
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from snownlp import SnowNLP

# ====== 情话API函数 ======
def get_love_message():
    """从API获取情话"""
    url = "https://api.vvhan.com/api/text/love?type=json"
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['data']['content']
            else:
                return "宝贝，我太想你了，脑子一片空白..."
        else:
            return "网络开小差了，但我对你的爱从不断线！"
    except Exception:
        return "我的心里全是你，连情话都害羞得躲起来了..."

# ====== 情感分析函数 ======
def analyze_sentiment(text):
    try:
        s = SnowNLP(text)
        return s.sentiments
    except:
        return 0.5  # 中性作为默认值

# ====== 创建情感仪表盘 ======
def create_sentiment_dashboard(scores):
    if not scores:
        return None
    
    # 计算平均情感分数
    avg_score = np.mean(scores)
    
    # 创建仪表盘
    fig = make_subplots(rows=1, cols=2, 
                        specs=[[{'type': 'indicator'}, {'type': 'indicator'}]],
                        column_widths=[0.5, 0.5])
    
    # 主仪表盘
    fig.add_trace(go.Indicator(
        mode="gauge+number",
        value=avg_score,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': "当前心情指数", 'font': {'size': 18}},
        gauge={
            'axis': {'range': [0, 1], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "hotpink"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 0.3], 'color': '#FF5252'},  # 红色表示消极
                {'range': [0.3, 0.7], 'color': '#FFD180'},  # 黄色表示中性
                {'range': [0.7, 1], 'color': '#69F0AE'}],  # 绿色表示积极
            'threshold': {
                'line': {'color': "black", 'width': 4},
                'thickness': 0.75,
                'value': avg_score}

        }
    ), row=1, col=1)
    
    # 情感状态指示器
    if avg_score > 0.7:
        mood = "😊 非常积极"
        color = "#4CAF50"
    elif avg_score > 0.55:
        mood = "🙂 积极"
        color = "#8BC34A"
    elif avg_score > 0.45:
        mood = "😐 中性"
        color = "#9E9E9E"
    elif avg_score > 0.3:
        mood = "😔 有点消极"
        color = "#FF9800"
    else:
        mood = "😢 非常消极"
        color = "#F44336"
    
    fig.add_trace(go.Indicator(
        mode="number",
        value=avg_score,
        number={'font': {'size': 40, 'color': color}},
        title={'text': mood, 'font': {'size': 18, 'color': color}},
        domain={'x': [0, 1], 'y': [0, 1]}
    ), row=1, col=2)
    
    fig.update_layout(
        height=250,
        margin=dict(l=20, r=20, t=60, b=20),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)'
    )
    
    return fig

# ====== 修复音乐问题 ======
# 使用session_state存储音乐状态
if 'music_playing' not in st.session_state:
    st.session_state.music_playing = False
    st.session_state.music_position = 0.0
    st.session_state.last_play_time = time.time()
# 在初始化部分添加以下状态变量
if 'last_tts_time' not in st.session_state:
    st.session_state.last_tts_time = 0  # 上次语音合成请求时间戳
if 'tts_cooldown' not in st.session_state:
    st.session_state.tts_cooldown = 5  # 冷却时间（秒）
if 'tts_processing' not in st.session_state:
    st.session_state.tts_processing = False  # 是否正在处理语音合成
if 'sentiment_scores' not in st.session_state:
    st.session_state.sentiment_scores = []  # 存储情感分数
if 'heart_clicked' not in st.session_state:
    st.session_state.heart_clicked = False  # 心形按钮点击状态

# 语音合成配置
tts_appid = 'd9ccf0b5'
tts_apikey = '9f3bd37c1b460f9b46731e0161e443a2'
tts_apisecret = 'OGIyMDliZjhiZjgzZTRmOTk0MjM2NzU2'
tts_res_id = '37fecaa_ttsclone-d9ccf0b5-hrotm'

# AI 配置
api_key = "sk-pjVb7YemscdeZANh11Ba625f9cE449439e742a9d16E94781"
api_base = "https://maas-api.cn-huabei-1.xf-yun.com/v1"
model_id = "xdeepseekr1qwen32b"
resource_id = "1942795537328791552"

client = OpenAI(api_key=api_key, base_url=api_base)

# system prompt（你的设定）
system_message = {
    "role": "system",
    "content": "你是常郅坤（id:三六），季婧雯（id:小比格狗）的男朋友，现在作为她的AI男友助手。你性格活泼、爱开玩笑、充满能量、工作认真、语言幽默、对她非常关心、偶尔爆粗口但情绪真挚。请尽可能贴近常郅坤原话风格表达。"
}

# 页面配置
st.set_page_config(
    page_title="ChatApp",
    page_icon="💬",
    layout="wide",
)

# 读取并编码音频文件
audio_file_path = "music/lovesong.mp3"
with open(audio_file_path, "rb") as f:
    audio_bytes = f.read()
    b64_audio = base64.b64encode(audio_bytes).decode()

# 创建右上角的心形按钮 - 使用Streamlit按钮替代HTML按钮
st.markdown("""
<style>
.heart-button {
    position: fixed;
    top: 200px;
    right: 100px;
    z-index: 1000;
    background: transparent;
    border: none;
    font-size: 40px;
    cursor: pointer;
    animation: heartbeat 1.5s infinite;
}
@keyframes heartbeat {
    0% { transform: scale(1); }
    15% { transform: scale(1.2); }
    30% { transform: scale(1); }
    45% { transform: scale(1.2); }
    60% { transform: scale(1); }
}
.heart-button:hover {
    color: #ff1493;
    animation: none;
    transform: scale(1.2);
}
</style>
""", unsafe_allow_html=True)

# 使用Streamlit按钮替代HTML按钮
heart_button = st.button("❤️", key="heart_button", help="点击听情话")
if heart_button:
    st.session_state.heart_clicked = True
    st.rerun()

# 处理心跳按钮点击
if st.session_state.get('heart_clicked'):
    # 获取情话
    love_text = get_love_message()
    
    # 设置语音合成
    st.session_state.tts_text = love_text
    st.session_state.play_tts = True
    st.session_state.last_tts_time = time.time()
    st.session_state.tts_processing = True
    st.session_state.heart_clicked = False
    
    # 添加情话到聊天历史
    st.session_state.history.append({
        "role": "assistant", 
        "content": love_text
    })
    
    st.rerun()

# 标题
st.markdown(
    """
    <h1 style='text-align: center; color: hotpink; font-size: 40px; font-family: "Segoe UI", sans-serif;'>
        🐣 鸡鸡歪的专属 AI 聊天机器人 💬
    </h1>
    """,
    unsafe_allow_html=True
)

# 页面按钮样式
st.markdown("""
<style>
.cute-music-button {
    background-color: hotpink;
    color: white;
    padding: 12px 26px;
    font-size: 18px;
    font-weight: bold;
    border: none;
    border-radius: 30px;
    cursor: pointer;
    box-shadow: 0 4px 6px rgba(0,0,0,0.2);
    transition: background-color 0.3s ease;
}
.cute-music-button:hover {
    background-color: deeppink;
}

/* 新增的语音按钮样式 */
.tts-button {
    background: none;
    border: none;
    color: #4CAF50;
    cursor: pointer;
    font-size: 16px;
    padding: 0;
    margin: 0;
    position: absolute;
    bottom: 8px;
    right: 8px;
    opacity: 0.7;
    transition: all 0.3s ease;
    z-index: 10;
}

.tts-button:hover {
    opacity: 1;
    transform: scale(1.2);
    color: #388E3C;
}

/* 消息容器添加相对定位 */
.message-container {
    position: relative;
    padding-bottom: 25px; /* 为按钮留出空间 */
}

/* 调整按钮样式 */
.stButton button {
    min-width: 0 !important;
    padding: 4px 8px !important;
    font-size: 14px !important;
}

/* 按钮容器样式 */
.button-container {
    position: absolute;
    bottom: 5px;
    right: 5px;
    z-index: 100;
}

/* 情感分析卡片样式 */
.sentiment-card {
    border: 1px solid #f0f0f0;
    padding: 12px;
    border-radius: 10px;
    background-color: #fff9fc;
    margin-bottom: 15px;
    box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
}
</style>
""", unsafe_allow_html=True)

# ====== 创建两列布局 - 音乐按钮 ======
col1, _ = st.columns([1, 1])  # 只保留音乐按钮列

with col1:
    # 音乐播放控制
    if st.session_state.music_playing:
        # 计算当前播放位置
        elapsed_time = time.time() - st.session_state.last_play_time
        current_position = st.session_state.music_position + elapsed_time
        
        # 嵌入带播放位置的音频
        components.html(f"""
        <audio id="bgmusic" autoplay style="display:none;">
            <source src="data:audio/mp3;base64,{b64_audio}" type="audio/mp3">
        </audio>
        <script>
            var audio = document.getElementById("bgmusic");
            audio.currentTime = {current_position};
            audio.play().catch(function(error) {{
                console.log("Autoplay failed:", error);
            }});
            
            // 更新播放位置
            setInterval(function() {{
                if (!audio.paused) {{
                    window.parent.postMessage({{
                        type: 'musicPosition',
                        position: audio.currentTime
                    }}, '*');
                }}
            }}, 1000);
        </script>
        """, height=0)
        
        # 音乐控制按钮
        if st.button("⏸️ 暂停背景音乐", key="pause_music"):
            st.session_state.music_playing = False
            st.rerun()
    else:
        # 音乐播放按钮
        if st.button("▶️ 播放背景音乐", key="play_music"):
            st.session_state.music_playing = True
            st.session_state.music_position = 0.0
            st.session_state.last_play_time = time.time()
            st.rerun()

# 从父窗口接收音乐位置更新
components.html("""
<script>
    window.addEventListener('message', function(event) {
        if (event.data.type === 'musicPosition') {
            window.parent.streamlitBridge.setComponentValue({
                position: event.data.position
            });
        }
    });
</script>
""", height=0)

# 获取天气信息（卡片美化）
def get_weather(city_code="101020100"):
    url = f"http://t.weather.itboy.net/api/weather/city/{city_code}"
    try:
        res = requests.get(url, timeout=5)
        res.raise_for_status()
        weather = res.json()

        city = weather["cityInfo"]["city"]
        update_time = weather["cityInfo"]["updateTime"]
        data = weather["data"]
        today = data["forecast"][0]

        wendu = data["wendu"]
        high = today["high"].replace("高温 ", "")
        low = today["low"].replace("低温 ", "")
        weather_type = today["type"]
        fx = today["fx"]
        fl = today["fl"]
        aqi = today.get("aqi", "N/A")

        weather_icon = "☀️" if "晴" in weather_type else "🌧️" if "雨" in weather_type else "⛅"

        html = f"""
        <div style="
            border: 1px solid #f0f0f0;
            padding: 12px;
            border-radius: 10px;
            background-color: #fff9fc;
            margin-bottom: 15px;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
        ">
            <div style='font-size:20px; font-weight:bold; color:#e91e63;'>📍 {city} 天气</div>
            <div style='margin-top:5px; font-size:15px;'>
                {weather_icon} <b>{weather_type}</b>　🌡️ {wendu}℃（{low} ~ {high})<br>
                💨 {fx} {fl}　🎯 AQI: <b>{aqi}</b><br>
                🕒 更新时间：{update_time}
            </div>
        </div>
        """
        return html

    except Exception:
        return "<div style='color: gray; margin-bottom:10px;'>⚠️ 无法获取天气信息</div>"

def get_daily_quote():
    url = "https://api.xygeng.cn/one"
    try:
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        result = response.json()

        if result["code"] == 200:
            data = result["data"]
            content = data["content"]
            origin = data["origin"]
            return f"""
            <div style="
                border: 1px solid #f0f0f0;
                padding: 12px;
                border-radius: 10px;
                background-color: #f9f9ff;
                margin-bottom: 15px;
                box-shadow: 2px 极 2px 6px rgba(0,0,0,0.05);
            ">
                <div style='font-size:16px; font-weight:bold; color:#3f51b5;'>📖 今天也要加油哦~</div>
                <div style='margin-top:6px; font-size:15px; color:#333;'>
                    “{content}”
                    <div style='margin-top:6px; font-size:13极; color:#888;'>—— {origin}</div>
                </div>
            </div>
            """
        else:
            return "<div style='color:gray;'>⚠️ 无法加载每日一句</div>"

    except Exception:
        return "<div style='color:gray;'>⚠️ 每日一句加载失败</div>"

# 日期计算
start_date = datetime(2024, 6, 1)
today = datetime.today()
days_together = (today - start_date).days

if today.month < 6 or (today.month == 6 and today.day < 1):
    next_anniversary = datetime(today.year, 6, 1)
else:
    next_anniversary = datetime(today.year + 1, 6, 1)

days_until_next_anniversary = (next_anniversary - today).days

# 初始化缓存数据（只运行一次）
if "weather_html" not in st.session_state:
    st.session_state.weather_html = get_weather().replace("font-size:16px", "font-size:20px")

if "daily_quote_html" not in st.session_state:
    st.session_state.daily_quote_html = get_daily_quote().replace("font-size:16px", "font-size:20px")

with st.sidebar:
    # 💗 我们的纪念日（在最上面）
    st.markdown(
        f"""
        <div style="
            border: 1px solid #f0f0f0;
            padding: 12px;
            border-radius: 10px;
            background-color: #fffef9;
            margin-bottom: 10px;
            box-shadow: 2px 2px 6px rgba(0,0,0,0.05);
        ">
            <div style='font-size:20px; font-weight:bold; color:#ff4081;'>💗 我们的纪念日</div>
            <div style='margin-top:6px; font-size:15px;'>
                已在一起：
                <span style='color:hotpink; font-weight:bold; font-size:18px'>
                    {days_together} 天
                </span><br>
                距下次周年：
                <span style='color:pink; font-weight:bold; font-size:18px'>
                    {days_until_next_anniversary} 天
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 📖 每日一句
    st.markdown(st.session_state.daily_quote_html, unsafe_allow_html=True)

    # 分割线
    st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

    # 🌤 天气卡片
    st.markdown(st.session_state.weather_html, unsafe_allow_html=True)

    # 分割线
    st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)
    # ====== 新增心情指示卡片 ======
    st.markdown(
        """
        <div class="sentiment-card">
            <div style='font-size:20px; font-weight:bold; color:#e91e63; text-align: center;'>💖 宝宝心情指示器</极div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # 显示心情仪表盘
    if st.session_state.sentiment_scores:
        dashboard_fig = create_sentiment_dashboard(st.session_state.sentiment_scores)
        if dashboard_fig:
            st.plotly_chart(dashboard_fig, use_container_width=True)
            
    else:
        st.info("还没有足够的数据来分析心情，请发送几条消息后再查看")

    # 分割线
    st.markdown("<hr style='margin: 12px 0; border: none; border-top: 1px dashed #ccc;'>", unsafe_allow_html=True)

    # 📷 图片模块标题
    st.markdown(
        """
        <div style='font-size:20px; font-weight:bold; color:#2196f3; margin-bottom:8px;'>📷 记录甜蜜瞬间</div>
        """,
        unsafe_allow_html=True
    )

    # 图片展示
    st.image("picture/11.png", caption="一起去看海")
    st.image("picture/12.png", caption="试试衣服")
    st.image("picture/13.png", caption="万圣节来啦！")
    st.image("picture/14.png", caption="常常过生日~")
    st.image("picture/15.png", caption="酷酷墨镜")
    st.image("picture/16.png", caption="可爱雷姆上线")

# 聊天记录初始化
if "history" not in st.session_state:
    st.session_state.history = []
    
# ====== 修复自动回复问题 ======
# 添加初始欢迎消息
if "first_run" not in st.session_state:
    st.session_state.first_run = True
    st.session_state.history.append({
        "role": "assistant", 
        "content": "宝宝，我是你的专属AI男友小常常，今天想我了吗？😘"
    })

# 页面样式 + 飘浮爱心
st.markdown(
    """
    <style>
    body {
        font-family: 'Arial', sans-serif;
        background-color: #f4f7f6;
    }
    h1 {
        color: #009688;
        font-family: 'Georgia', serif;
        text-align: center;
        font-size: 2.5rem;
        margin-bottom: 30px;
    }
    .chat-message {
        border-radius: 15px;
        padding: 12px;
        margin-bottom: 12px;
        width: auto;
        min-width: 160px;
        max-width: 85%;
        word-wrap: break-word;
        white-space: normal;
        font-size: 1rem;
        line-height: 1.5;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .user-message {
        background-color: #e1f5fa;
        border: 1px solid #b3e5fc;
        color: #01579a;
    }
    .assistant-message {
        background-color: #f1f8e9;
        border: 1px solid #c5e1a5;
        color: #33691e;
    }
    .user-name, .assistant-name {
        font-size: 14px;
        margin-bottom: 5px;
        font-weight: bold;
    }
    .user-name {
        color: #00796b;
    }
    .assistant-name {
        color: #33691e;
    }
    .footer-text {
        position: fixed;
        bottom: 10px;
        right: 10px;
        font-size: 12px;
        color: #888888;
        background-color: rgba(255, 255, 255, 0.7);
        padding: 5px;
        border-radius: 5px;
        z-index: 9999;
    }

    /* 飘浮爱心动画 */
    .floating-heart {
        position: fixed;
        bottom: -50px;
        font-size: 24px;
        color: hotpink;
        animation: floatUp 8s linear infinite;
        opacity: 0.6;
        z-index: 9998;
        pointer-events: none;
    }
    @keyframes floatUp {
        0%   { transform: translateY(0) scale(1); opacity: 0.6; }
        50%  { transform: translateY(-400px) scale(1.3); opacity: 1; }
        100% { transform: translateY(-900px) scale(0.7); opacity: 0; }
    }
    .heart1  { left: 5%;  animation-delay: 0s; }
    .heart2  { left: 15%; animation-delay: 1.5s; }
    .heart3  { left: 25%; animation-delay: 3s; }
    .heart4  { left: 35%; animation-delay: 0.8s; }
    .heart5  { left: 45%; animation-delay: 2.2s; }
    .heart6  { left: 55%; animation-delay: 4s; }
    .heart7  { left: 65%; animation-delay: 1s; }
    .heart8  { left: 75%; animation-delay: 3.2s; }
    .heart9  { left: 85%; animation-delay: 0.5s; }
    .heart10 { left: 95%; animation-delay: 2.8s; }
    .heart11 { left: 50%; animation-delay: 1.3s; font-size: 30px; }
    .heart12 { left: 30%; animation-delay: 4.5s; font-size: 28px; }
    </style>

    <div class="floating-heart heart1">❤️</div>
    <div class="floating-heart heart2">💖</div>
    <div class="floating-heart heart3">💘</div>
    <div class="floating-heart heart4">💗</div>
    <div class="floating-heart heart5">❤️</div>
    <div class="floating-heart heart6">💞</div>
    <div class="floating-heart heart7">💓</div>
    <div class="floating-heart heart8">❤️</div>
    <div class="floating-heart heart9">💝</div>
    <div class="floating-heart heart10">💖</div>
    <div class="floating-heart heart11">❤️</div>
    <div class="floating-heart heart12">💗</div>
    """,
    unsafe_allow_html=True
)

# 聊天显示
for idx, message in enumerate(st.session_state.history):
    if message["role"] == "user":
        with st.chat_message("user", avatar="picture/1.jpg"):
            st.markdown('<div class="user-name">我(*´∀*)（季婧雯）</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-message user-message">{message["content"]}</div>', unsafe_allow_html=True)
    else:
        with st.chat_message("assistant", avatar="picture/2.jpg"):
            # 使用相对定位的容器
            st.markdown('<div class="message-container">', unsafe_allow_html=True)
            st.markdown('<div class="assistant-name">宝宝(*^_^*)（常郅坤）</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="chat-message assistant-message">{message["content"]}</div>', unsafe_allow_html=True)
            
            # 添加语音按钮容器
            st.markdown('<div class="button-container">', unsafe_allow_html=True)
            
            # 只在最新消息后显示说话按钮
            if idx == len(st.session_state.history) - 1 and message["role"] == "assistant":
                current_time = time.time()
                # 检查是否在冷却时间内或正在处理
                if (current_time - st.session_state.last_tts_time < st.session_state.tts_cooldown or 
                    st.session_state.tts_processing):
                    # 显示禁用状态的按钮
                    st.button('⏳', key=f'speak_button_{idx}', help="请稍后再试")
                else:
                    if st.button('🔊', key=f'speak_button_{idx}', help="播放语音"):
                        # 修复缩进错误的部分
                        st.session_state.tts_text = message["content"]
                        st.session_state.play_tts = True
                        st.session_state.last_tts_time = current_time
                        st.session_state.tts_processing = True

                    
            st.markdown('</div>', unsafe_allow_html=True)  # 关闭按钮容器
            st.markdown('</div>', unsafe_allow_html=True)  #消息容器

def get_response_material(user_query, history):
    try:
        # 构造带历史的 messages
        messages = [system_message]
        for msg in history:
            if msg["role"] in ["user", "assistant"]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_query})

        # 调用模型
        response = client.chat.completions.create(
            model=model_id,
            messages=messages,
            stream=False,
            temperature=0.7,
            max_tokens=2048,
            extra_headers={"lora_id": resource_id},
            stream_options={"include_usage": True},
            extra_body={"search_disable": False, "show_ref_label": True}
        )

        reply = response.choices[0].message.content
        return reply

    except Exception as e:
        return f"出错了：{e}", "⚠️ 无法获取模型回复"

# 语音合成类
class TTSProcessor:
    def __init__(self):
        self.audio_file = "tts_output.mp3"
        self.tts_complete = False
        self.tts_error = None
        
    def assemble_ws_auth_url(self, url, api_key, api_secret):
        if "://" not in url: 
            raise ValueError("Invalid URL")
        protocol, rest = url.split("://", 1)
        if "/" not in rest: 
            host, path = rest, "/"
        else: 
            host, path = rest.split("/", 1)
        path = "/" + path if path else "/"
        
        date = format_date_time(mktime(datetime.now().timetuple()))
        sign_str = f"host: {host}\ndate: {date}\nGET {path} HTTP/1.1"
        signature = hmac.new(
            api_secret.encode(), 
            sign_str.encode(), 
            hashlib.sha256
        ).digest()
        signature = base64.b64encode(signature).decode()
        auth = f'api_key="{api_key}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'
        auth_b64 = base64.b64encode(auth.encode()).decode()
        
        return f"{url}?{urlencode({'host': host, 'date': date, 'authorization': auth_b64})}"
    
    def on_message(self, ws, message):
        try:
            msg = json.loads(message)
            code, sid = msg["header"]["code"], msg["header"]["sid"]
            if code != 0: 
                self.tts_error = f"Error: {msg.get('message', 'Unknown error')} (Code: {code}, SID: {sid})"
                ws.close()
                return
            
            if "payload" in msg and "audio" in msg["payload"]:
                audio_data = base64.b64decode(msg["payload"]["audio"]["audio"])
                with open(self.audio_file, 'ab') as f: 
                    f.write(audio_data)
                
                if msg["payload"]["audio"].get("status") == 2: 
                    self.tts_complete = True
                    ws.close()
        except Exception as e: 
            self.tts_error = f"处理消息异常: {e}"
            ws.close()

    def on_error(self, ws, error): 
        self.tts_error = f"连接错误: {error}"
        ws.close()

    def on_close(self, ws, *args): 
        pass

    def on_open(self, ws):
        def run():
            data = json.dumps({
                "header": self.wsParam.CommonArgs,
                "parameter": self.wsParam.BusinessArgs,
                "payload": self.wsParam.Data
            })
            ws.send(data)
            if os.path.exists(self.audio_file): 
                os.remove(self.audio_file)
        threading.Thread(target=run).start()

    def text_to_speech(self, text):
        class WsParam:
            def __init__(self, APPID, APIKey, APISecret, Text, res_id):
                self.CommonArgs = {"app_id": APPID, "res_id": res_id, "status": 2}
                self.BusinessArgs = {"tts": {
                    "vcn": "x5_clone", "volume": 50, "rhy": 0, "pybuffer": 1, 
                    "speed": 50, "pitch": 50, "bgs": 0, "reg": 0, "rdn": 0,
                    "audio": {"encoding": "lame", "sample_rate": 16000, 
                              "channels": 1, "bit_depth": 16, "frame_size": 0},
                    "pybuf": {"encoding": "utf8", "compress": "raw", "format": "plain"}
                }}
                self.Data = {"text": {
                    "encoding": "utf8", "compress": "raw", "format": "plain", 
                    "status": 2, "seq": 0, 
                    "text": base64.b64encode(text.encode()).decode()
                }}
        
        self.wsParam = WsParam(tts_appid, tts_apikey, tts_apisecret, text, tts_res_id)
        
        # 生成带认证的WebSocket URL
        wsUrl = self.assemble_ws_auth_url(
            'wss://cn-huabei-1.xf-yun.com/v1/private/voice_clone', 
            tts_apikey, 
            tts_apisecret
        )
        
        # 重置状态
        self.tts_complete = False
        self.tts_error = None
        
        # 创建WebSocket连接
        ws = websocket.WebSocketApp(
            wsUrl, 
            on_message=self.on_message, 
            on_error=self.on_error, 
            on_close=self.on_close
        )
        ws.on_open = self.on_open
        
        # 运行WebSocket
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        
        # 检查结果
        if self.tts_error:
            return False, self.tts_error
        return True, "语音合成成功"

# 初始化语音合成器
if 'tts_processor' not in st.session_state:
    st.session_state.tts_processor = TTSProcessor()

# 语音合成状态
if 'play_tts' not in st.session_state:
    st.session_state.play_tts = False
if 'tts_text' not in st.session_state:
    st.session_state.tts_text = ""

# 聊天输入
user_input = st.chat_input("请输入消息...")

if user_input:
    # 保存用户输入
    st.session_state.history.append({"role": "user", "content": user_input})
    
    # ====== 新增情感分析 ======
    # 分析当前消息情感
    sentiment_score = analyze_sentiment(user_input)
    
    # 更新情感分数列表（只保留最新的5条）
    st.session_state.sentiment_scores.append(sentiment_score)
    if len(st.session_state.sentiment_scores) > 5:
        st.session_state.sentiment_scores = st.session_state.sentiment_scores[-5:]
    
    # 显示用户消息
    with st.chat_message("user", avatar="picture/1.jpg"):
        st.markdown('<div class="user-name">我(*´∀*)（季婧雯）</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-message user-message">{user_input}</div>', unsafe_allow_html=True)

    # 获取回复
    response = get_response_material(user_input, st.session_state.history)

    # 显示助手回复
    with st.chat_message("assistant", avatar="picture/2.jpg"):
        # 使用相对定位的容器
        st.markdown('<div class="message-container">', unsafe_allow_html=True)
        st.markdown('<div class="assistant-name">宝宝(*^_^*)（常郅坤）</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-message assistant-message">{response}</div>', unsafe_allow_html=True)
        
        # 添加语音按钮容器
        st.markdown('<div class="button-container">', unsafe_allow_html=True)
        
        # 添加说话按钮
        current_time = time.time()
        # 检查是否在冷却时间内或正在处理
        if (current_time - st.session_state.last_tts_time < st.session_state.tts_cooldown or 
            st.session_state.tts_processing):
            # 显示禁用状态的按钮
            st.button('⏳', key='speak_button_new', help="请稍后再试")
        else:
            if st.button('🔊', key='speak_button_new', help="播放语音"):
                st.session_state.tts_text = response
                st.session_state.play_tts = True
                st.session_state.last_tts_time = current_time
                st.session_state.tts_processing = True
            
        st.markdown('</div>', unsafe_allow_html=True)  # 关闭按钮容器
        st.markdown('</div>', unsafe_allow_html=True)  # 关闭消息容器
    
    # 保存助手回复
    st.session_state.history.append({"role": "assistant", "content": response})

    # 限制历史记录长度
    if len(st.session_state.history) > 20:
        st.session_state.history = st.session_state.history[-20:]
        
    # 更新音乐播放位置
    if st.session_state.music_playing:
        # 计算播放时间
        elapsed_time = time.time() - st.session_state.last_play_time
        st.session_state.music_position += elapsed_time
        st.session_state.last_play_time = time.time()

# 处理语音合成
if st.session_state.play_tts and st.session_state.tts_text:
    try:
        with st.spinner('正在合成语音...'):
            # 调用语音合成
            success, message = st.session_state.tts_processor.text_to_speech(st.session_state.tts_text)
            
            if success:
                # 播放合成的语音
                with open("tts_output.mp3", "rb") as f:
                    audio_bytes = f.read()
                    st.audio(audio_bytes, format='audio/mp3', start_time=0)
                st.success("语音播放中...")
            else:
                st.error(f"语音合成失败: {message}")
    except Exception as e:
        st.error(f"语音合成过程中发生错误: {e}")
    finally:
        # 重置状态
        st.session_state.play_tts = False
        st.session_state.tts_text = ""
        st.session_state.tts_processing = False  # 重置处理状态

# 页脚
st.markdown(
    '<div class="footer-text">本聊天ai机器人基于Deepseek_R1基座采用常郅坤与季婧雯聊天语料微调生成，知识产权为二者共有，侵权必追究法律责任</div>',
    unsafe_allow_html=True
)
