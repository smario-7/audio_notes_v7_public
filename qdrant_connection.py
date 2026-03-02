"""
Moduł do obsługi połączenia z bazą Qdrant z obsługą błędów i UI Streamlit
"""
import streamlit as st
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import ApiException
import logging

logger = logging.getLogger(__name__)


def load_qdrant_credentials():
    """
    Ładuje poświadczenia Qdrant z secrets.toml lub sesji Streamlit
    
    Returns:
        tuple: (qdrant_url, qdrant_api_key) lub (None, None) jeśli brak
    """
    qdrant_url = None
    qdrant_api_key = None
    
    try:
        qdrant_url = st.secrets.get("qdrant_url") or st.secrets.get("QDRANT_URL")
        qdrant_api_key = st.secrets.get("qdrant_api_key") or st.secrets.get("QDRANT_API_KEY")

        if qdrant_url and qdrant_api_key:
            logger.info("✓ Poświadczenia załadowane z secrets")
            return qdrant_url, qdrant_api_key
    except Exception as e:
        logger.warning(f"Nie udało się załadować secrets: {e}")
    
    # Spróbuj załadować z session state
    if "qdrant_url" in st.session_state and "qdrant_api_key" in st.session_state:
        qdrant_url = st.session_state.qdrant_url
        qdrant_api_key = st.session_state.qdrant_api_key
        
        if qdrant_url and qdrant_api_key:
            logger.info("✓ Poświadczenia załadowane z session state")
            return qdrant_url, qdrant_api_key
    
    return None, None


def test_qdrant_connection(qdrant_url, qdrant_api_key):
    """
    Testuje połączenie z bazą Qdrant
    
    Args:
        qdrant_url: URL bazy Qdrant
        qdrant_api_key: Klucz API Qdrant
        
    Returns:
        bool: True jeśli połączenie udane, False w innym wypadku
    """
    try:
        client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
            timeout=5.0
        )
        # Spróbuj pobrać informacje o serwerze
        client.get_collections()
        logger.info("✓ Pomyślne połączenie z Qdrant")
        return True
    except ApiException as e:
        logger.error(f"Błąd API Qdrant: {e}")
        return False
    except Exception as e:
        logger.error(f"Błąd połączenia z Qdrant: {e}")
        return False


def display_qdrant_config_form():
    """
    Wyświetla formularz do konfiguracji Qdrant
    """
    st.subheader("Konfiguracja Qdrant")

    with st.form("qdrant_config_form"):
        qdrant_url = st.text_input(
            "QDRANT_URL",
            value=st.session_state.get("qdrant_url", ""),
            placeholder="http://localhost:6333",
            help="Adres URL serwera Qdrant"
        )
        qdrant_api_key = st.text_input(
            "QDRANT_API_KEY",
            value=st.session_state.get("qdrant_api_key", ""),
            type="password",
            placeholder="Wpisz swój klucz API",
            help="Klucz API do autoryzacji w Qdrant"
        )
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("🔗 Testuj połączenie")
        with col2:
            clear_clicked = st.form_submit_button("🔄 Wyczyść dane")

    if submitted:
        url = qdrant_url.strip()
        key = qdrant_api_key.strip()
        if not url or not key:
            st.error("❌ Proszę uzupełnić oba pola!")
        else:
            with st.spinner("Testowanie połączenia..."):
                if test_qdrant_connection(url, key):
                    st.session_state.qdrant_url = url
                    st.session_state.qdrant_api_key = key
                    st.session_state.qdrant_connected = True
                    st.success("✅ Pomyślnie połączono z Qdrant!")
                    st.rerun()
                else:
                    st.error(
                        "❌ Nie udało się połączyć z Qdrant. Sprawdź:\n"
                        "- Czy URL jest poprawny?\n"
                        "- Czy serwer Qdrant jest dostępny?\n"
                        "- Czy klucz API jest prawidłowy?"
                    )

    if clear_clicked:
        st.session_state.qdrant_url = ""
        st.session_state.qdrant_api_key = ""
        st.session_state.qdrant_connected = False
        st.info("Dane zostały wyczyszczone")
        st.rerun()


def initialize_qdrant():
    """
    Inicjalizuje połączenie z Qdrant lub wyświetla formularz konfiguracji
    
    Returns:
        QdrantClient: Zainitialized client lub None jeśli błąd
    """
    # Inicjalizuj session state
    if "qdrant_connected" not in st.session_state:
        st.session_state.qdrant_connected = False
    if "qdrant_url" not in st.session_state:
        st.session_state.qdrant_url = ""
    if "qdrant_api_key" not in st.session_state:
        st.session_state.qdrant_api_key = ""
    
    # Spróbuj załadować poświadczenia z secrets
    qdrant_url, qdrant_api_key = load_qdrant_credentials()
    
    if qdrant_url and qdrant_api_key:
        if test_qdrant_connection(qdrant_url, qdrant_api_key):
            st.session_state.qdrant_url = qdrant_url
            st.session_state.qdrant_api_key = qdrant_api_key
            st.session_state.qdrant_connected = True
            return QdrantClient(url=qdrant_url, api_key=qdrant_api_key)
        else:
            # Błąd połączenia - wyświetl formularz
            display_qdrant_error_message()
            display_qdrant_config_form()
            return None
    
    # Brak poświadczeń - wyświetl formularz
    display_qdrant_error_message()
    display_qdrant_config_form()
    return None


def display_qdrant_error_message():
    """
    Wyświetla przyjazny dla użytkownika komunikat o błędzie
    """
    st.warning(
        "⚠️ **Nie udało się nawiązać połączenia z bazą Qdrant**\n\n"
        "Aby aplikacja mogła działać, musisz skonfigurować połączenie do Qdrant. "
        "Możesz to zrobić na dwa sposoby:\n\n"
        "1. **Automatycznie** (zalecane): Dodaj do pliku `.streamlit/secrets.toml`:\n"
        "```\n"
        "qdrant_url = \"http://localhost:6333\"\n"
        "qdrant_api_key = \"your-api-key\"\n"
        "```\n\n"
        "2. **Ręcznie**: Wpisz poniżej swoje dane dostępu"
    )


def get_qdrant_client():
    """
    Zwraca zainitializowany klient Qdrant lub None
    
    Returns:
        QdrantClient: Zainitialized client lub None
    """
    if st.session_state.get("qdrant_connected", False):
        try:
            return QdrantClient(
                url=st.session_state.qdrant_url,
                api_key=st.session_state.qdrant_api_key
            )
        except Exception as e:
            logger.error(f"Błąd przy tworzeniu klienta Qdrant: {e}")
            st.session_state.qdrant_connected = False
            return None
    
    return None