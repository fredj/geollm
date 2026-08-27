import asyncio
import contextlib
import logging
import os
import time
from collections.abc import AsyncIterable
from typing import Annotated, Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.sse import EventSourceResponse
from langchain.chat_models import init_chat_model
from langchain_core.rate_limiters import InMemoryRateLimiter
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from pydantic import BaseModel, Field

from etter.datasources import CompositeDataSource, IGNBDCartoSource, PostGISDataSource, SwissNames3DSource
from etter.datasources.ign_bdcarto import IGN_BDCARTO_TYPE_MAP
from etter.datasources.swissnames3d import OBJEKTART_TYPE_MAP
from etter.models import GeoQuery
from etter.parser import GeoFilterParser
from etter.spatial import apply_spatial_relation

# Load environment variables
load_dotenv()

logger = logging.getLogger("uvicorn")

geo_mcp = FastMCP("etter MCP Server", stateless_http=True, json_response=True)


@contextlib.asynccontextmanager
async def lifespan(_app: FastAPI):
    await asyncio.to_thread(datasource.preload)
    async with geo_mcp.session_manager.run():
        yield


app = FastAPI(title="etter Demo", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data source configuration
#
# When ETTER_DB_URL is set the demo uses PostGISDataSource (DB-backed).
# Otherwise it falls back to the original file-based sources (SwissNames3D
# shapefiles and IGN BD-CARTO GeoPackages).

ETTER_DB_URL = os.getenv("ETTER_DB_URL")

sources = []

if ETTER_DB_URL:
    SWISSNAMES3D_TABLE = os.getenv("SWISSNAMES3D_TABLE", "swissnames3d")
    IGN_BDCARTO_TABLE = os.getenv("IGN_BDCARTO_TABLE", "ign_bdcarto")
    DB_SCHEMA = os.getenv("DB_SCHEMA", "public")

    swissnames_table = f"{DB_SCHEMA}.{SWISSNAMES3D_TABLE}"
    sources.append(
        PostGISDataSource(
            connection=ETTER_DB_URL,
            table=swissnames_table,
            type_map=OBJEKTART_TYPE_MAP,
        )
    )

    bdcarto_table = f"{DB_SCHEMA}.{IGN_BDCARTO_TABLE}"
    sources.append(
        PostGISDataSource(
            connection=ETTER_DB_URL,
            table=bdcarto_table,
            type_map=IGN_BDCARTO_TYPE_MAP,
        )
    )
else:
    SWISSNAMES3D_PATH = os.getenv("SWISSNAMES3D_PATH", "data")
    IGN_BDCARTO_PATH = os.getenv("IGN_BDCARTO_PATH", "data/bdcarto")

    if not os.path.exists(SWISSNAMES3D_PATH):
        raise RuntimeError(
            f"SwissNames3D data not found at {SWISSNAMES3D_PATH}. "
            "Set SWISSNAMES3D_PATH or provide ETTER_DB_URL for PostGIS mode."
        )

    sources.append(SwissNames3DSource(SWISSNAMES3D_PATH))

    if os.path.exists(IGN_BDCARTO_PATH):
        try:
            ign_source = IGNBDCartoSource(IGN_BDCARTO_PATH)
            ign_source.get_available_types()
            sources.append(ign_source)
        except ValueError as e:
            logger.warning("IGN BD-CARTO not loaded: %s", e)
    else:
        logger.warning("IGN BD-CARTO path not found (%s), skipping.", IGN_BDCARTO_PATH)

datasource = CompositeDataSource(*sources)

# Initialize etter components
LLM_API_KEY = os.getenv("LLM_API_KEY")
if not LLM_API_KEY:
    raise RuntimeError("LLM_API_KEY not set. Please set it in your .env file.")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
llm_rate_limiter = InMemoryRateLimiter(requests_per_second=0.5, max_bucket_size=5)
llm = init_chat_model(
    model=LLM_MODEL, temperature=0, api_key=LLM_API_KEY, max_tokens=600, rate_limiter=llm_rate_limiter
)
parser = GeoFilterParser(llm, datasource=datasource)


def _build_result_features(geo_query, reference_features: list) -> list:
    """Build a flat list of (search_area, reference) Feature dicts for the given query."""
    geometries = [f["geometry"] for f in reference_features]
    search_area = apply_spatial_relation(geometries, geo_query.spatial_relation, geo_query.buffer_config)
    result_features = [
        {
            "type": "Feature",
            "geometry": search_area,
            "properties": {
                "role": "search_area",
                "relation": geo_query.spatial_relation.relation,
                "reference_name": reference_features[0]["properties"]["name"] if reference_features else None,
            },
        }
    ]
    result_features.extend(reference_features)
    return result_features


async def _run_geo_query(query: str) -> "QueryResponse":
    """Parse a natural-language query and resolve it to a QueryResponse.

    Raises:
        ValueError: if the reference location is not found in the datasource.
    """
    geo_query = await parser.aparse(query)
    location_name = geo_query.reference_location.name
    features = datasource.search(location_name, type=geo_query.reference_location.type)
    if not features:
        raise ValueError(f"Location '{location_name}' not found")
    result_features = _build_result_features(geo_query, features)
    feature_collection = {"type": "FeatureCollection", "features": result_features}
    return QueryResponse(query=query, geo_query=geo_query, result=feature_collection)


QueryString = Annotated[str, Field(min_length=1, max_length=300)]


class QueryRequest(BaseModel):
    query: QueryString


class QueryResponse(BaseModel):
    query: str
    geo_query: GeoQuery
    result: dict[str, Any]  # GeoJSON FeatureCollection


@app.post("/api/query")
async def process_query(request: QueryRequest) -> QueryResponse:
    try:
        return await _run_geo_query(request.query)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Error processing query")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/query/stream", response_class=EventSourceResponse)
async def process_query_stream(request: QueryRequest) -> AsyncIterable[dict[str, Any]]:
    """
    Stream processing of a geographic query with real-time reasoning and results.

    Returns Server-Sent Events (SSE) with two event types:
    - reasoning: Intermediate processing steps from the LLM
    - data-response: Final GeoQuery result and feature collection

    Example usage:
        curl -X POST http://localhost:8000/api/query/stream \
             -H "Content-Type: application/json" \
             -d '{"query":"restaurants near Lake Geneva"}' \
             --no-buffer
    """
    try:
        geo_query_result = None

        # Stream parsing events
        parse_start = time.perf_counter()
        async for event in parser.parse_stream(request.query):
            yield event

            if event["type"] == "data-response":
                geo_query_result = event["content"]
        yield {"type": "reasoning", "content": "LLM parsing", "duration_ms": (time.perf_counter() - parse_start) * 1000}

        if geo_query_result:
            yield {"type": "reasoning", "content": "Resolving location in database"}

            geo_query = GeoQuery.model_validate(geo_query_result)

            location_name = geo_query.reference_location.name
            search_start = time.perf_counter()
            logger.info(f"Searching for location: {location_name} with type hint: {geo_query.reference_location.type}")
            features = datasource.search(location_name, type=geo_query.reference_location.type)
            logger.info(
                f"Found {len(features)} features for location '{location_name}' in {time.perf_counter() - search_start:.2f} seconds"
            )
            logger.info(f"Features properties: {[f['properties'] for f in features]}")

            if not features:
                yield {"type": "reasoning", "content": f"Location not found: {location_name}"}
                yield {"type": "error", "content": f"Location not found: {location_name}"}
                return

            yield {
                "type": "reasoning",
                "content": f"Found {len(features)} matching location(s)",
                "duration_ms": (time.perf_counter() - search_start) * 1000,
            }

            yield {"type": "reasoning", "content": "Computing spatial search areas"}

            spatial_start = time.perf_counter()
            result_features = _build_result_features(geo_query, features)
            spatial_duration = (time.perf_counter() - spatial_start) * 1000
            yield {"type": "reasoning", "content": "Computed spatial relations", "duration_ms": spatial_duration}

            feature_collection = {
                "type": "FeatureCollection",
                "features": result_features,
            }

            final_response = {
                "query": request.query,
                "geo_query": geo_query_result,
                "result": feature_collection,
            }

            yield {"type": "reasoning", "content": "Query processing completed"}
            yield {"type": "result", "content": final_response}
            yield {"type": "finish"}

    except Exception as e:
        logger.exception("Error during streaming")
        yield {"type": "error", "content": f"Error during streaming: {str(e)}"}


@geo_mcp.tool()
async def parse_geo_query(user_query: QueryString) -> dict[str, Any]:
    """
    Transforms natural language location queries into structured geographic filters
    that can be used by search engines and spatial databases.

    Args:
        user_query: The natural language query describing the geographic filter,
            e.g. "Find all locations within walking distance from Zurich main railway station"
    """
    try:
        return (await _run_geo_query(user_query)).model_dump()
    except ValueError as e:
        raise ToolError(str(e))


# Mount MCP server (streamable_http_path="/" so endpoint is /mcp, not /mcp/mcp)
geo_mcp.settings.streamable_http_path = "/"
app.mount("/mcp", geo_mcp.streamable_http_app())

# Serve the frontend (low-priority route, matched after API routes)
app.frontend("/", directory="demo/static")
