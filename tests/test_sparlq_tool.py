import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from aioresponses import aioresponses
from tools.spendcast import SPARQLTool

from dotenv import load_dotenv
from pathlib import Path 
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env.test")


@pytest.mark.asyncio
async def test_arun_success():
    tool = SPARQLTool()

    query = "SELECT * WHERE {?s ?p ?o} LIMIT 10"
    result = await tool._arun(query)

    # Assert
    assert "results" in result

