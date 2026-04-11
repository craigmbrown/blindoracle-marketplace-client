"""BlindOracle Marketplace Client SDK."""

from blindoracle_client.client import BlindOracleClient

__version__ = "0.1.0"
__all__ = ["BlindOracleClient"]

# Framework integrations (imported lazily to avoid hard deps)
# from blindoracle_client.integrations.langchain_tools import get_blindoracle_tools
# from blindoracle_client.integrations.crewai_tools import blindoracle_compliance_check
# from blindoracle_client.integrations.autogen_tools import register_blindoracle_tools
