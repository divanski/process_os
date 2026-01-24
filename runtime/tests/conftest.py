"""
ProcessOS Runtime Tests - Pytest Configuration

Defines custom markers and shared fixtures for the test suite.
"""



def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "real_llm: tests requiring real LLM (skip unless PROCESSOS_LLM_ENABLED=true)"
    )
