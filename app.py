from hashlib import md5
import uuid
import streamlit as st
from streamlit import session_state as ss, toast
from io import BytesIO
from audiorecorder import audiorecorder
from dotenv import dotenv_values
from openai import OpenAI
from qdrant_client.models import PointStruct, Distance, VectorParams
from qdrant_connection import initialize_qdrant, get_qdrant_client

env = dotenv_values(".env")

EMBEDDING_MODEL = "text-embedding-3-large"

EMBEDDING_DIM = 3072

AUDIO_TRANSCRIBE_MODEL = "whisper-1"

QDRANT_COLLECTION_NAME = "AudioNotes"

def get_openai_client():
    return OpenAI(api_key = ss["openai_api_key"])

def transcribe_audio(audio_bytes):
    openai_client = get_openai_client()
    audio_file = BytesIO(audio_bytes)
    audio_file.name = "audio.mp3"
    transcript = openai_client.audio.transcriptions.create(
        file = audio_file,
        model = AUDIO_TRANSCRIBE_MODEL,
        response_format = "verbose_json"
    )
    return transcript.text

#
# DB
#

def assure_db_collection_exists():
    qdrant_client = get_qdrant_client()
    if not qdrant_client.collection_exists(QDRANT_COLLECTION_NAME):
        qdrant_client.create_collection(
            collection_name=QDRANT_COLLECTION_NAME,
            vectors_config=VectorParams(
                size=EMBEDDING_DIM,
                distance=Distance.COSINE
            )
        )

def get_embedding(text):
    openai_client = get_openai_client()
    result = openai_client.embeddings.create(
        input = [text],
        model = EMBEDDING_MODEL,
        dimensions = EMBEDDING_DIM
    )

    return result.data[0].embedding

def add_note_to_db(note_text):
    qdrant_client = get_qdrant_client()
    point_uuid = str(uuid.uuid4())
    qdrant_client.upsert(
        collection_name = QDRANT_COLLECTION_NAME,
        points = [
            PointStruct(
                id = point_uuid,
                vector = get_embedding(note_text),
                payload = {
                    "text" : note_text
                }
            )
        ]   
    )

def list_notes_from_db(query = None):
    qdrant_client = get_qdrant_client()
    if not query:
        notes = qdrant_client.scroll(collection_name = QDRANT_COLLECTION_NAME, limit = 10)[0]
        result = []
        for note in notes:
            result.append({
                "id": note.id,
                "text": note.payload["text"],
                "score": None
            })
        return result

    else:
        notes = qdrant_client.query_points(
            collection_name = QDRANT_COLLECTION_NAME,
            query = get_embedding(query),
            limit = 10
        )
        result = []
        for note in notes.points:
            result.append({
                "id": note.id,
                "text": note.payload["text"],
                "score": note.score
            })
        return result

def remove_note_from_db(note_id):
    """
    Usuwamy notatę z bazy danych
    """
    qdrant_client = get_qdrant_client()
    # Delete the note with the given ID from the Qdrant collection
    qdrant_client.delete(
        collection_name=QDRANT_COLLECTION_NAME,
        points_selector=[note_id]
    )

def remove_all_notes_from_db():
    qdrant_client = get_qdrant_client()

    # Usunięcie wszystkich punktów z kolekcji
    qdrant_client.delete_collection(
        collection_name=QDRANT_COLLECTION_NAME
    )

    st.success("Wszystkie notatki zostały usunięte.")


#
# MAIN
#

st.set_page_config(page_title = "Audio Notatki", layout = "centered")

# openai API protection
if not ss.get("openai_api_key"):
    if "OPENAI_API_KEY" in env:
        ss["openai_api_key"] = env["OPENAI_API_KEY"]
    else:
        st.info("Podaj swój klucz API OpenAI aby móc korzystac z tej aplikacji")
        ss["openai_api_key"] = st.text_input("Klucz API od OpenAI", type = "password")
        if ss["openai_api_key"]:
            st.rerun()

if not ss.get("openai_api_key"):
    st.stop()

# Session state initialization
if "note_audio_bytes_md5" not in ss:
    ss["note_audio_bytes_md5"] = None

if "note_audio_bytes" not in ss:
    ss["note_audio_bytes"] = None

if "note_text" not in ss:
    ss["note_text"] = ""

if "note_audio_text" not in ss:
    ss["note_audio_text"] = ""

st.title("Audio Notes")

qdrant_client = initialize_qdrant()
if qdrant_client is None:
    st.error(
        "❌ Aplikacja wymaga połączenia z bazą Qdrant\n\n"
        "Proszę skonfiguruj poświadczenia w formularzu powyżej"
    )
    st.stop()

assure_db_collection_exists()

add_tab, search_tab, delete_tab= st.tabs(["Dodaj notatkę", "Wyszukaj notatkę", "Czyszczenie bazy"])

with add_tab:
    note_audio = audiorecorder(
        start_prompt = "Nagraj notatkę",
        stop_prompt = "Zatrzymanie nagrywanie"
    )

    if note_audio:
        audio = BytesIO()
        note_audio.export(audio, format = "mp3")
        ss["note_audio_bytes"] = audio.getvalue()
        current_md5 = md5(ss["note_audio_bytes"]).hexdigest()
        if ss["note_audio_bytes_md5"] != current_md5:
            ss["note_audio_text"] = ""
            ss["note_text"] = ""
            ss["note_audio_bytes_md5"] = current_md5
        
        st.audio(ss["note_audio_bytes"], format = "audio/mp3")

        if st.button("Transrybuj audio"):
            ss["note_audio_text"] = transcribe_audio(ss["note_audio_bytes"])

        if ss["note_audio_text"]:
            ss["note_text"] = st.text_area("Edytuj notatkę", value = ss.get("note_tex",ss["note_audio_text"]))
        
        if ss["note_text"] and st.button("Zapisz notatkę", disabled = not ss["note_text"]):
            add_note_to_db(note_text = ss["note_text"])
            st.toast("Notatka zapisana", icon = ":material/add:")
            
with search_tab:
    query = st.text_input("Wyszukaj notatkę")
    
    if st.button("Szukaj"):
        notes = list_notes_from_db(query)
        for note in notes:
            with st.container(border = True):
                st.markdown(note["text"])
                col0, col1 = st.columns([7, 1])
                with col0:
                    if note["score"]:
                        st.markdown(f":violet[{note['score']}]")
                with col1:
                    if st.button(
                        "Usuń", 
                        key=f"delete_{note['id']}", 
                        on_click=remove_note_from_db, 
                        args=(note["id"],)
                        ):
                        st.toast("Usunięto notatkę", icon = ":material/delete:")
                        # st.rerun()
with delete_tab:
    notes = list_notes_from_db()
    for note in notes:
        col1, col2 = st.columns([7, 1])
        with col1:
            st.markdown(note["text"])
        with col2:
            if st.button("Usuń", key=f"del_{note['id']}", use_container_width=True):
                remove_note_from_db(note["id"])
                st.toast("Usunięto notatkę", icon=":material/delete:")
                st.rerun()
    with st.popover("Usuń wszystkie notatki"):
        if st.button("Tak", use_container_width=True):
            remove_all_notes_from_db()
            st.toast("Usunięto wszystkie notatki", icon=":material/delete:")
    