"""Diagnostic tests to identify the root cause of query failures"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from config import config
from ai_generator import AIGenerator
import ssl
import socket


class TestDiagnostics:
    """Diagnostic tests to identify issues"""

    def test_api_key_present(self):
        """Test that API key is configured"""
        print("\n=== API Key Configuration ===")
        print(f"OPENROUTER_API_KEY present: {bool(config.OPENROUTER_API_KEY)}")
        print(f"OPENROUTER_BASE_URL: {config.OPENROUTER_BASE_URL}")
        print(f"Default model: {config.DEFAULT_MODEL}")
        print(f"Fallback models: {config.FALLBACK_MODELS[:3]}")

        assert config.OPENROUTER_API_KEY, "API key is missing"

    def test_network_connectivity(self):
        """Test basic network connectivity to OpenRouter"""
        print("\n=== Network Connectivity Test ===")

        import urllib.parse
        parsed = urllib.parse.urlparse(config.OPENROUTER_BASE_URL)
        host = parsed.hostname
        port = 443

        print(f"Testing connection to {host}:{port}")

        try:
            sock = socket.create_connection((host, port), timeout=10)
            sock.close()
            print("✓ TCP connection successful")
        except Exception as e:
            print(f"✗ TCP connection failed: {e}")
            pytest.fail(f"Cannot connect to {host}:{port}")

    def test_ssl_context(self):
        """Test SSL/TLS configuration"""
        print("\n=== SSL/TLS Configuration ===")

        print(f"Default SSL context: {ssl.create_default_context()}")
        print(f"SSL version: {ssl.OPENSSL_VERSION}")

        import urllib.parse
        parsed = urllib.parse.urlparse(config.OPENROUTER_BASE_URL)
        host = parsed.hostname

        try:
            context = ssl.create_default_context()
            with socket.create_connection((host, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=host) as ssock:
                    print(f"✓ SSL handshake successful")
                    print(f"SSL version: {ssock.version()}")
                    print(f"Cipher: {ssock.cipher()}")
        except ssl.SSLError as e:
            print(f"✗ SSL error: {e}")
            print("\nThis is the root cause of the query failures!")
        except Exception as e:
            print(f"✗ Connection error: {e}")

    @pytest.mark.skipif(not config.OPENROUTER_API_KEY, reason="No API key")
    def test_simple_api_call(self):
        """Test a simple API call without tools"""
        print("\n=== Simple API Call Test ===")

        ai_gen = AIGenerator(
            api_key=config.OPENROUTER_API_KEY,
            base_url=config.OPENROUTER_BASE_URL,
            model=config.DEFAULT_MODEL,
            fallback_models=config.FALLBACK_MODELS
        )

        try:
            response = ai_gen.generate_response(
                query="What is 2+2? Answer with just the number.",
                tools=None,
                tool_manager=None
            )

            print(f"Response: {response}")

            if response.startswith("Error"):
                print("\n✗ API call failed with error")
                print(f"Error message: {response}")
                # Extract the specific error
                if "CERTIFICATE_VERIFY_FAILED" in response:
                    print("\n🔍 ROOT CAUSE: SSL certificate verification is failing")
                    print("This prevents all API calls to OpenRouter from succeeding")
            else:
                print("✓ API call successful")

        except Exception as e:
            print(f"✗ Exception: {e}")
            import traceback
            print(traceback.format_exc())


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
