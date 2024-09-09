import openai
from openai import OpenAI
import json
import requests
from bs4 import BeautifulSoup
from googlesearch import search
import pandas as pd

import queue
import re
import sys
import time

from google.cloud import speech
import pyaudio

import streamlit as st
import threading

# Audio recording parameters
RATE = 16000
CHUNK = int(RATE / 10)  # 100ms

# List to store fact-checking results
results = []

class MicrophoneStream:
    """Opens a recording stream as a generator yielding the audio chunks."""

    def __init__(self: object, rate: int = RATE, chunk: int = CHUNK) -> None:
        """The audio -- and generator -- is guaranteed to be on the main thread."""
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self: object) -> object:
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1,
            rate=self._rate,
            input=True,
            frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(
        self: object,
        type: object,
        value: object,
        traceback: object,
    ) -> None:
        """Closes the stream, regardless of whether the connection was lost or not."""
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(
        self: object,
        in_data: object,
        frame_count: int,
        time_info: object,
        status_flags: object,
    ) -> object:
        """Continuously collect data from the audio stream, into the buffer.

        Args:
            in_data: The audio data as a bytes object
            frame_count: The number of frames captured
            time_info: The time information
            status_flags: The status flags

        Returns:
            The audio data as a bytes object
        """
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self: object) -> object:
        """Generates audio chunks from the stream of audio data in chunks.

        Args:
            self: The MicrophoneStream object

        Returns:
            A generator that outputs audio chunks.
        """
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b"".join(data)


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

def fact_check_text(text):
    knowledge_base = retrieve_kb(text)
    prompt = f"Please fact-check the following statement:\n\n{text}\n\nProvide a summary of the accuracy and any corrections. Here is a knowledge base you can use: {knowledge_base}."
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a fact checker. When you get a message, use your own knowledge base along with the knowledge base provided to output a response in JSON format (do not include ```json) with whether the statement is true or false, and the reason for your determination. The JSON keys should be statement, isTrue and reason. Do not fact-check the statement if it appears to be a question posed by a moderator in a debate."}, 
            {"role": "user", "content": prompt}
        ]
    )
    return response.choices[0].message.content.strip()

def listen_print_loop(responses: object) -> str:
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.

    Args:
        responses: List of server responses

    Returns:
        The transcribed text.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript

        overwrite_chars = " " * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + "\r")
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            text = transcript + overwrite_chars
            print(text)
            def thread_task(text):
                response = fact_check_text(text)
                result = json.loads(response)
                results.insert(0, result)
                print(result)
    
            if len(text.split(" ")) > 3:
                thread = threading.Thread(target=thread_task, args=(text,))
                thread.start()
                print("Thread started")

            # Exit recognition
            if re.search(r"\b(exit|quit)\b", transcript, re.I):
                print("Exiting..")
                break

            num_chars_printed = 0

    return transcript


def transcribe_and_fact_check() -> None:
    """Transcribe speech from audio file."""
    language_code = "en-US"  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = speech.RecognitionConfig(
        encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code,
    )

    streaming_config = speech.StreamingRecognitionConfig(
        config=config, interim_results=True
    )

    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (
            speech.StreamingRecognizeRequest(audio_content=content)
            for content in audio_generator
        )

        responses = client.streaming_recognize(streaming_config, requests)

        listen_print_loop(responses)

def main():

    global results
    
    st.title("YouTube Live Stream Fact-Checking")

    url = st.sidebar.text_input("Enter YouTube Live Stream Embed URL", "https://www.youtube.com/embed/live_stream?channel=CHANNEL_ID")
    st.markdown(f"""
<iframe width="560" height="315" src="{url}" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>
""", unsafe_allow_html=True)


    st.subheader("Fact-Check Results")
    #result_df = pd.DataFrame(results_table, columns=["Statement", "IsTrue", "Reason"])
    #st.table(result_df)

    placeholder = st.empty()

    df = pd.DataFrame(results)
    placeholder.table(df)


    def transcribe_and_fact_check():
        language_code = "en-US"
        client = speech.SpeechClient()
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=RATE,
            language_code=language_code,
        )
        streaming_config = speech.StreamingRecognitionConfig(
            config=config, interim_results=True
        )

        with MicrophoneStream(RATE, CHUNK) as stream:
            audio_generator = stream.generator()
            requests = (
                speech.StreamingRecognizeRequest(audio_content=content)
                for content in audio_generator
            )
            responses = client.streaming_recognize(streaming_config, requests)
            try:
                listen_print_loop(responses)
            except Exception:
                transcribe_and_fact_check()
    
    if st.button("Start Transcription and Fact-Checking"):
        threading.Thread(target=transcribe_and_fact_check, daemon=True).start()

    while True:
        if results:
            df = pd.DataFrame(results)
            placeholder.table(df)
        time.sleep(1)

main()
