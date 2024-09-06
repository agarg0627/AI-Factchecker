import moviepy.editor as mp
import openai
from openai import OpenAI
import speech_recognition as sr
from pydub import AudioSegment
import os
import json
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import streamlit as st
import pandas as pd

openai.api_key = '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'
client = OpenAI(api_key=openai.api_key)

# Function to search news articles
def search_google_news(query, num_results=5):
    search_query = f"{query} news"
    search_results = search(search_query, num_results=num_results)
    return list(search_results)

# Function to extract article content
def extract_article_content(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    title = soup.title.string if soup.title else "No title"
    paragraphs = soup.find_all('p')
    article_content = ' '.join([para.get_text() for para in paragraphs])
    return title, article_content

# Function to retrieve knowledge base
def retrieve_kb(keyword):
    num_articles = 2
    knowledge_base = {}
    news_articles = search_google_news(keyword, num_results=num_articles)
    for article_url in news_articles:
        title, content = extract_article_content(article_url)
        knowledge_base[title] = content
    return knowledge_base

# Function to extract audio from video
def extract_audio_from_video(video_path, audio_path):
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path)

# Function to convert audio to text
def convert_audio_to_text(audio_path):
    recognizer = sr.Recognizer()
    audio = sr.AudioFile(audio_path)
    with audio as source:
        audio_content = recognizer.record(source)
    return recognizer.recognize_google(audio_content)

# Function to fact-check text using GPT
def fact_check_text(text):
    knowledge_base = retrieve_kb(text)
    prompt = f"Please fact-check the following statement:\n\n{text}\n\nProvide a summary of the accuracy and any corrections. Here is a knowledge base you can use: {knowledge_base}."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a fact checker. When you get a message, use your own knowledge base along with searching online to output a response in JSON format with whether the statement is true or false, and the reason for your determination. The JSON keys should be statement, isTrue, and reason."}, 
            {"role": "user", "content": prompt}
        ]
    )
    return json.loads(response.choices[0].message.content.strip())

# Function to process video for fact-checking
def process_video_for_fact_checking(video_path):
    audio_path = "temp_audio.wav"
    extract_audio_from_video(video_path, audio_path)
    text = convert_audio_to_text(audio_path)
    fact_checked_text = fact_check_text(text)
    os.remove(audio_path)
    return fact_checked_text

# Initialize Streamlit app
st.title("Real-Time Fact-Checker")

# Text input for video link
user_input = st.text_input("Enter an embedded video link:")
url = user_input

# Display video
st.title("Display of Your Video")
st.markdown(f"""
    <div style="display: flex; justify-content: center;">
        <iframe width="560" height="315" src="{url}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
    </div>
""", unsafe_allow_html=True)

# Initialize empty DataFrame to store fact-check results
if "fact_check_results" not in st.session_state:
    st.session_state.fact_check_results = pd.DataFrame(columns=["Statement", "Is True?", "Reason"])

# Function to update the DataFrame
def update_fact_check_results(response):
    new_row = {
        "Statement": response["statement"],
        "Is True?": response["isTrue"],
        "Reason": response["reason"]
    }
    st.session_state.fact_check_results = st.session_state.fact_check_results.append(new_row, ignore_index=True)

# Example of fact-checking a sample statement
response = fact_check_text("Former President Donald Trump cut overtime benefits for millions of workers.")
update_fact_check_results(response)

# Display the updated DataFrame
st.dataframe(st.session_state.fact_check_results)

# Layout for detailed information display
col1, col2, col3 = st.columns([3, 1, 4])

# Display each column's information based on response
if len(st.session_state.fact_check_results) > 0:
    latest_result = st.session_state.fact_check_results.iloc[-1]
    
    with col1:
        st.subheader("Statement")
        st.write(latest_result["Statement"])
    
    with col2:
        st.subheader("Is True?")
        st.write(latest_result["Is True?"])
    
    with col3:
        st.subheader("Reason")
        st.write(latest_result["Reason"])
