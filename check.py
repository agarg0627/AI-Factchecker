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

def search_google_news(query, num_results=5):
    # Using Google Search to get the top news articles URLs
    # Adding "news" to the query to focus on news articles
    search_query = f"{query} news"
    search_results = search(search_query, num_results=num_results)
    return list(search_results)

def extract_article_content(url):
    # Request the article webpage
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')

    # Extract the title
    title = soup.title.string if soup.title else "No title"

    # Extract the article content by looking for <p> tags
    paragraphs = soup.find_all('p')
    article_content = ' '.join([para.get_text() for para in paragraphs])

    return title, article_content

def retrieve_kb(keyword):
    num_articles = 2
    knowledge_base = {}
    news_articles = search_google_news(keyword, num_results=num_articles)

    for article_url in news_articles:
        title, content = extract_article_content(article_url)
        knowledge_base[title] = content

    return knowledge_base

def extract_audio_from_video(video_path, audio_path):
    video = mp.VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path)

def convert_audio_to_text(audio_path):
    recognizer = sr.Recognizer()
    audio = sr.AudioFile(audio_path)
    with audio as source:
        audio_content = recognizer.record(source)
    return recognizer.recognize_google(audio_content)

def fact_check_text(text):
    knowledge_base = retrieve_kb(text)
    prompt = f"Please fact-check the following statement:\n\n{text}\n\nProvide a summary of the accuracy and any corrections. Here is a knowledge base you can use: {knowledge_base}."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a fact checker. When you get a message, use your own knowledge base along with searching online to output a response in JSON format (do not include ```json) with whether the statement is true or false, and the reason for your determination. The JSON keys should be statement, isTrue and reason."}, 
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def process_video_for_fact_checking(video_path):
    audio_path = "temp_audio.wav"
    
    extract_audio_from_video(video_path, audio_path)
    
    text = convert_audio_to_text(audio_path)
    
    fact_checked_text = fact_check_text(text)
    
    os.remove(audio_path)
    
    return fact_checked_text

video_path = 'video.mp4'

#result = process_video_for_fact_checking(video_path)
response = fact_check_text("Former President Donald Trump cut overtime benefits for millions of workers.")
result = json.loads(response)
#print(result)
#print("Fact-checking Result:")

st.title("Start with a Video to Check")
user_input = st.text_input("Enter an embedded video link:")
url = user_input

st.title("Display of Your Video")
#display debate video here 

# YouTube video URL
#youtube_url = "https://www.youtube.com/embed/Rus0ght1j34?si=l9zQ1mG_xK9bHcmC"  

# Embed YouTube video in an iframe
st.markdown(f"""
<iframe width="560" height="315" src="{url}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
""", unsafe_allow_html=True)

# Pass result to a dataframe

df = pd.DataFrame(result, index=[0])


st.dataframe(df)
