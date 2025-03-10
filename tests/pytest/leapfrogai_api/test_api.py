import json
import os
import shutil
import time
from typing import Optional

import pytest
from fastapi.applications import BaseHTTPMiddleware
from fastapi.security import HTTPBearer
from fastapi.testclient import TestClient
from starlette.middleware.base import _CachedRequest
from supabase import ClientOptions
from leapfrogai_api.typedef.chat import ChatCompletionRequest, ChatMessage
from leapfrogai_api.typedef.completion import CompletionRequest
from leapfrogai_api.typedef.embeddings import CreateEmbeddingRequest
from leapfrogai_api.main import app
from leapfrogai_api.routers.supabase_session import init_supabase_client

security = HTTPBearer()

# Set environment variables that the TestClient will use
LFAI_CONFIG_FILENAME = os.environ["LFAI_CONFIG_FILENAME"] = "repeater-test-config.yaml"
LFAI_CONFIG_PATH = os.environ["LFAI_CONFIG_PATH"] = os.path.join(
    os.path.dirname(__file__), "fixtures"
)
LFAI_CONFIG_FILEPATH = os.path.join(LFAI_CONFIG_PATH, LFAI_CONFIG_FILENAME)

MODEL = "repeater"
TEXT_INPUT = (
    "This is the input content for completions, embeddings, and chat completions"
)
TEXT_INPUT_LEN = len(TEXT_INPUT)

#########################
#########################


class AsyncClient:
    """Supabase client class."""

    def __init__(
        self,
        supabase_url: str,
        supabase_key: str,
        access_token: Optional[str] = None,
        options: ClientOptions = ClientOptions(),
    ):
        self.supabase_url = supabase_url
        self.supabase_key = supabase_key
        self.access_token = access_token
        self.options = options


async def mock_init_supabase_client() -> AsyncClient:
    return AsyncClient("", "", "", ClientOptions())


async def pack_dummy_bearer_token(request: _CachedRequest, call_next):
    request.headers._list.append(
        (
            "authorization".encode(),
            "Bearer dummy".encode(),
        )
    )
    return await call_next(request)


def load_audio_file(path: str):
    file_path = os.path.join("tests", "data", path)
    with open(file_path, "rb") as file:
        return file.read()


@pytest.fixture
def dummy_auth_middleware():
    app.dependency_overrides[init_supabase_client] = mock_init_supabase_client
    app.user_middleware.clear()
    app.middleware_stack = None
    app.add_middleware(BaseHTTPMiddleware, dispatch=pack_dummy_bearer_token)
    app.middleware_stack = app.build_middleware_stack()


def test_config_load():
    """Test that the config is loaded correctly."""
    with TestClient(app) as client:
        response = client.get("/leapfrogai/v1/models")

        assert response.status_code == 200
        expected_response = {
            "config_sources": {"repeater-test-config.yaml": [MODEL]},
            "models": {MODEL: {"backend": "localhost:50051", "name": MODEL}},
            "directory": LFAI_CONFIG_PATH,
            "filename": LFAI_CONFIG_FILENAME,
        }
        assert response.json() == expected_response


def test_config_delete(tmp_path):
    """Test that the config is deleted correctly."""
    # Move repeater-test-config.yaml to temp dir so that we can remove it at a later step
    tmp_config_filepath = shutil.copyfile(
        LFAI_CONFIG_FILEPATH, os.path.join(tmp_path, LFAI_CONFIG_FILENAME)
    )
    os.environ["LFAI_CONFIG_PATH"] = str(tmp_path)

    with TestClient(app) as client:
        # Ensure the API loads the temp config
        response = client.get("/leapfrogai/v1/models")
        assert response.status_code == 200

        expected_response = {
            "config_sources": {"repeater-test-config.yaml": [MODEL]},
            "models": {MODEL: {"backend": "localhost:50051", "name": MODEL}},
            "directory": os.environ["LFAI_CONFIG_PATH"],
            "filename": LFAI_CONFIG_FILENAME,
        }
        assert response.json() == expected_response

        # Delete source config from temp dir
        os.remove(tmp_config_filepath)

        # Wait for the API to detect the change
        time.sleep(0.5)

        # Assert response is now empty
        response = client.get("/leapfrogai/v1/models")
        assert response.status_code == 200
        expected_empty_response = {
            "config_sources": {},
            "models": {},
            "directory": os.environ["LFAI_CONFIG_PATH"],
            "filename": LFAI_CONFIG_FILENAME,
        }
        assert response.json() == expected_empty_response

    # Reset the environment variable
    os.environ["LFAI_CONFIG_PATH"] = os.path.join(os.path.dirname(__file__), "fixtures")


def test_routes():
    """Test that the expected routes are present."""
    expected_routes = {
        "/docs": ["GET", "HEAD"],
        "/healthz": ["GET"],
        "/leapfrogai/v1/models": ["GET"],
        "/openai/v1/models": ["GET"],
        "/openai/v1/completions": ["POST"],
        "/openai/v1/chat/completions": ["POST"],
        "/openai/v1/embeddings": ["POST"],
        "/openai/v1/audio/transcriptions": ["POST"],
        "/openai/v1/audio/translations": ["POST"],
        "/openai/v1/files": ["POST"],
        "/openai/v1/assistants": ["POST"],
        "/leapfrogai/v1/count/tokens": ["POST"],
    }

    openai_routes = [
        ("/openai/v1/files", "upload_file", ["POST"]),
        ("/openai/v1/files", "list_files", ["GET"]),
        ("/openai/v1/files/{file_id}", "retrieve_file", ["GET"]),
        ("/openai/v1/files/{file_id}", "delete_file", ["DELETE"]),
        ("/openai/v1/files/{file_id}/content", "retrieve_file_content", ["GET"]),
        ("/openai/v1/assistants", "create_assistant", ["POST"]),
        ("/openai/v1/assistants", "list_assistants", ["GET"]),
        ("/openai/v1/assistants/{assistant_id}", "retrieve_assistant", ["GET"]),
        ("/openai/v1/assistants/{assistant_id}", "modify_assistant", ["POST"]),
        ("/openai/v1/assistants/{assistant_id}", "delete_assistant", ["DELETE"]),
        ("/openai/v1/vector_stores", "create_vector_store", ["POST"]),
        ("/openai/v1/vector_stores", "list_vector_stores", ["GET"]),
        (
            "/openai/v1/vector_stores/{vector_store_id}",
            "retrieve_vector_store",
            ["GET"],
        ),
        ("/openai/v1/vector_stores/{vector_store_id}", "modify_vector_store", ["POST"]),
        (
            "/openai/v1/vector_stores/{vector_store_id}",
            "delete_vector_store",
            ["DELETE"],
        ),
        (
            "/openai/v1/vector_stores/{vector_store_id}/files",
            "create_vector_store_file",
            ["POST"],
        ),
        (
            "/openai/v1/vector_stores/{vector_store_id}/files",
            "list_vector_store_files",
            ["GET"],
        ),
        (
            "/openai/v1/vector_stores/{vector_store_id}/files/{file_id}",
            "retrieve_vector_store_file",
            ["GET"],
        ),
        (
            "/openai/v1/vector_stores/{vector_store_id}/files/{file_id}",
            "delete_vector_store_file",
            ["DELETE"],
        ),
    ]

    actual_routes = app.routes
    for route in actual_routes:
        if hasattr(route, "path") and route.path in expected_routes:
            assert route.methods == set(expected_routes[route.path])
            del expected_routes[route.path]

    for route, name, methods in openai_routes:
        found = False
        for actual_route in actual_routes:
            if (
                hasattr(actual_route, "path")
                and actual_route.path == route
                and actual_route.name == name
            ):
                assert actual_route.methods == set(methods)
                found = True
                break
        assert found, f"Missing route: {route}, {name}, {methods}"

    assert len(expected_routes) == 0


def test_healthz():
    """Test the healthz endpoint."""
    with TestClient(app) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_embedding(dummy_auth_middleware):
    """Test the embedding endpoint."""
    expected_embedding = [0.0 for _ in range(10)]

    with TestClient(app) as client:
        # Send request to client
        embedding_request = CreateEmbeddingRequest(
            model=MODEL,
            input=TEXT_INPUT,
        )
        response = client.post(
            "/openai/v1/embeddings", json=embedding_request.model_dump()
        )
        assert response.status_code == 200

        # parse through the response
        response_obj = response.json()
        assert "data" in response_obj
        assert len(response_obj.get("data")) == 1

        # validate the expected response
        data_obj = response_obj.get("data")[0]
        assert "embedding" in data_obj
        assert data_obj.get("embedding") == expected_embedding


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_transcription(dummy_auth_middleware):
    """Test the transcription endpoint."""
    expected_transcription = "The repeater model received a transcribe request"

    with TestClient(app) as client:
        audio_filename = "0min12sec.wav"
        audio_content = load_audio_file(audio_filename)
        files = {"file": (audio_filename, audio_content, "audio/mpeg")}
        data = {"model": MODEL}
        response = client.post(
            "/openai/v1/audio/transcriptions", files=files, data=data
        )

        assert response.status_code == 200

        response_obj = response.json()
        assert response_obj["text"] == expected_transcription


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_translation(dummy_auth_middleware):
    """Test the translation endpoint."""
    expected_translation = "The repeater model received a translation request"

    with TestClient(app) as client:
        audio_filename = "arabic-audio.wav"
        audio_content = load_audio_file(audio_filename)
        files = {"file": (audio_filename, audio_content, "audio/mpeg")}
        data = {"model": MODEL}
        response = client.post("/openai/v1/audio/translations", files=files, data=data)

        assert response.status_code == 200

        response_obj = response.json()
        assert response_obj["text"] == expected_translation


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_completion(dummy_auth_middleware):
    """Test the completion endpoint."""
    with TestClient(app) as client:
        completion_request = CompletionRequest(
            model=MODEL,
            prompt=TEXT_INPUT,
        )
        response = client.post(
            "/openai/v1/completions", json=completion_request.model_dump()
        )
        assert response.status_code == 200

        assert response

        # parse through the completion response
        response_obj = response.json()
        assert "choices" in response_obj

        # parse the choices from the response
        response_choices = response_obj.get("choices")
        assert len(response_choices) == 1
        assert "text" in response_choices[0]

        # parse finish reason
        assert "finish_reason" in response_choices[0]
        assert "stop" == response_choices[0].get("finish_reason")
        # parse usage data
        response_usage = response_obj.get("usage")
        prompt_tokens = response_usage.get("prompt_tokens")
        completion_tokens = response_usage.get("completion_tokens")
        total_tokens = response_usage.get("total_tokens")
        assert prompt_tokens == TEXT_INPUT_LEN
        assert completion_tokens == TEXT_INPUT_LEN
        assert total_tokens == TEXT_INPUT_LEN * 2

        # validate that the repeater repeated
        assert response_choices[0].get("text") == TEXT_INPUT


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_stream_completion(dummy_auth_middleware):
    """Test the stream completion endpoint."""
    with TestClient(app) as client:
        completion_request = CompletionRequest(
            model=MODEL, prompt=TEXT_INPUT, stream=True
        )

        response = client.post(
            "/openai/v1/completions", json=completion_request.model_dump()
        )
        assert response.status_code == 200
        assert (
            response.headers.get("content-type") == "text/event-stream; charset=utf-8"
        )

        # parse through the streamed response
        iter_length = 0
        iter_lines = response.iter_lines()
        for line in iter_lines:
            # skip the empty, and non-data lines
            if ": " in line:
                strings = line.split(": ", 1)

                # Process all the data responses that is not the sig_stop signal
                if strings[0] == "data" and strings[1] != "[DONE]":
                    stream_response = json.loads(strings[1])
                    assert "choices" in stream_response
                    choices = stream_response.get("choices")
                    assert len(choices) == 1
                    iter_length += 1
                    # parse finish reason
                    assert "finish_reason" in choices[0]
                    # in streaming responses, the stop reason is not STOP until the last iteration (token) is sent back
                    if iter_length == TEXT_INPUT_LEN:
                        assert "stop" == choices[0].get("finish_reason")
                    else:
                        assert None is choices[0].get("finish_reason")
                    # parse usage data
                    response_usage = stream_response.get("usage")
                    prompt_tokens = response_usage.get("prompt_tokens")
                    completion_tokens = response_usage.get("completion_tokens")
                    total_tokens = response_usage.get("total_tokens")
                    # in streaming responses, the length is not returned until the last iteration (token) is sent back
                    if iter_length == TEXT_INPUT_LEN:
                        assert prompt_tokens == TEXT_INPUT_LEN
                        assert completion_tokens == TEXT_INPUT_LEN
                        assert total_tokens == TEXT_INPUT_LEN * 2
                    else:
                        assert total_tokens == 0
                        assert completion_tokens == 0
                        assert total_tokens == 0

        # The repeater only responds with 1 message, the exact one that was prompted
        assert iter_length == TEXT_INPUT_LEN


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_chat_completion(dummy_auth_middleware):
    """Test the chat completion endpoint."""
    with TestClient(app) as client:
        input_content = "this is the chat completion input."
        chat_completion_request = ChatCompletionRequest(
            model=MODEL,
            messages=[ChatMessage(role="user", content=input_content)],
        )
        response = client.post(
            "/openai/v1/chat/completions", json=chat_completion_request.model_dump()
        )
        assert response.status_code == 200

        assert response

        # parse through the chat completion response
        response_obj = response.json()
        assert "choices" in response_obj

        # parse the choices from the response
        response_choices = response_obj.get("choices")
        assert len(response_choices) == 1
        assert "message" in response_choices[0]
        assert "content" in response_choices[0].get("message")

        # parse finish reason
        assert "finish_reason" in response_choices[0]
        assert "stop" == response_choices[0].get("finish_reason")

        # parse usage data
        response_usage = response_obj.get("usage")
        prompt_tokens = response_usage.get("prompt_tokens")
        completion_tokens = response_usage.get("completion_tokens")
        total_tokens = response_usage.get("total_tokens")
        assert prompt_tokens == len(input_content)
        assert completion_tokens == len(input_content)
        assert total_tokens == len(input_content) * 2

        # validate that the repeater repeated
        assert response_choices[0].get("message").get("content") == input_content


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_stream_chat_completion(dummy_auth_middleware):
    """Test the stream chat completion endpoint."""
    with TestClient(app) as client:
        input_content = "this is the stream chat completion input."
        input_length = len(input_content)

        chat_completion_request = ChatCompletionRequest(
            model=MODEL,
            messages=[ChatMessage(role="user", content=input_content)],
            stream=True,
        )

        response = client.post(
            "/openai/v1/chat/completions", json=chat_completion_request.model_dump()
        )
        assert response.status_code == 200
        assert (
            response.headers.get("content-type") == "text/event-stream; charset=utf-8"
        )

        # parse through the streamed response
        iter_length = 0
        iter_lines = response.iter_lines()
        for line in iter_lines:
            # skip the empty, and non-data lines
            if ": " in line:
                strings = line.split(": ", 1)

                # Process all the data responses that is not the sig_stop signal
                if strings[0] == "data" and strings[1] != "[DONE]":
                    stream_response = json.loads(strings[1])
                    assert "choices" in stream_response
                    choices = stream_response.get("choices")
                    assert len(choices) == 1
                    assert "delta" in choices[0]
                    assert "content" in choices[0].get("delta")
                    assert (
                        choices[0].get("delta").get("content")
                        == input_content[iter_length]
                    )
                    iter_length += 1
                    # parse finish reason
                    assert "finish_reason" in choices[0]
                    # in streaming responses, the stop reason is not STOP until the last iteration (token) is sent back
                    if iter_length == input_length:
                        assert "stop" == choices[0].get("finish_reason")
                    else:
                        assert None is choices[0].get("finish_reason")
                    # parse usage data
                    response_usage = stream_response.get("usage")
                    prompt_tokens = response_usage.get("prompt_tokens")
                    completion_tokens = response_usage.get("completion_tokens")
                    total_tokens = response_usage.get("total_tokens")
                    # in streaming responses, the length is not returned until the last iteration (token) is sent back
                    if iter_length == input_length:
                        assert prompt_tokens == input_length
                        assert completion_tokens == input_length
                        assert total_tokens == input_length * 2
                    else:
                        assert total_tokens == 0
                        assert completion_tokens == 0
                        assert total_tokens == 0

        # The repeater only responds with 1 message, the exact one that was prompted
        assert iter_length == input_length


@pytest.mark.skipif(
    os.environ.get("LFAI_RUN_REPEATER_TESTS") != "true",
    reason="LFAI_RUN_REPEATER_TESTS envvar was not set to true",
)
def test_token_count(dummy_auth_middleware):
    """Test the token count endpoint."""
    with TestClient(app) as client:
        input_text = "This is a test sentence for token counting."
        token_count_request = {"model": "repeater", "text": input_text}
        response = client.post("/leapfrogai/v1/count/tokens", json=token_count_request)
        assert response.status_code == 200

        response_data = response.json()
        assert "token_count" in response_data
        assert isinstance(response_data["token_count"], int)
        assert response_data["token_count"] == len(input_text)
