"""
Web Search Service
Provides real-time information from the internet for weather, news, 
sports, currency rates, etc. Uses only free APIs.

Services:
- DuckDuckGo Instant Answers: General web search (no API key)
- Open-Meteo: Weather forecasts (free, no key)
- NewsData.io: Latest news (free tier, 200 req/day)
"""

import re
from typing import Any

import httpx
import structlog
from duckduckgo_search import AsyncDDGS

from app.core.config import settings

logger = structlog.get_logger(__name__)


class WebSearchService:
    """
    Aggregated web search service that intelligently routes queries
    to the most appropriate free data source.
    """

    def __init__(self) -> None:
        self._http = httpx.AsyncClient(timeout=10.0)

    async def search(self, query: str) -> str | None:
        """
        Perform an intelligent web search for the given query.
        Automatically detects the query type and routes to the best source.

        Args:
            query: Natural language search query.

        Returns:
            Formatted string with search results, or None on failure.
        """
        query_lower = query.lower()

        # Route to specialized sources first
        if self._is_weather_query(query_lower):
            result = await self._get_weather(query)
            if result:
                return result

        if self._is_news_query(query_lower) and settings.NEWS_API_KEY:
            result = await self._get_news(query)
            if result:
                return result

        # General DuckDuckGo search (free, no API key)
        result = await self._duckduckgo_search(query)
        return result

    async def _duckduckgo_search(self, query: str) -> str | None:
        """
        Search DuckDuckGo and return formatted results.
        Completely free, no API key needed.
        """
        try:
            async with AsyncDDGS() as ddgs:
                results = await ddgs.atext(
                    query,
                    max_results=settings.MAX_SEARCH_RESULTS,
                    safesearch="off",
                )

            if not results:
                return None

            # Format results
            formatted_parts = []
            for i, result in enumerate(results[:3], 1):
                title = result.get("title", "")
                body = result.get("body", "")[:300]
                href = result.get("href", "")
                formatted_parts.append(f"{i}. **{title}**\n{body}\n{href}")

            formatted = "\n\n".join(formatted_parts)
            logger.info(
                "DuckDuckGo search complete",
                query=query,
                results=len(results),
            )
            return formatted

        except Exception as e:
            logger.error("DuckDuckGo search failed", query=query, error=str(e))
            return None

    async def _get_weather(self, query: str) -> str | None:
        """
        Get weather data from Open-Meteo (free, no API key required).
        Geocodes the city name first, then fetches weather.
        """
        try:
            # Extract city from query
            city = self._extract_city(query)
            if not city:
                return None

            # Geocode city to lat/lng
            geo_url = f"{settings.GEOCODING_API_URL}?name={city}&count=1&language=en&format=json"
            geo_resp = await self._http.get(geo_url)
            geo_data = geo_resp.json()

            if not geo_data.get("results"):
                return await self._duckduckgo_search(query)  # Fall back to web search

            location = geo_data["results"][0]
            lat = location["latitude"]
            lng = location["longitude"]
            location_name = f"{location['name']}, {location.get('country', '')}"

            # Fetch weather
            weather_url = (
                f"{settings.WEATHER_API_URL}"
                f"?latitude={lat}&longitude={lng}"
                f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,"
                f"weather_code,apparent_temperature,precipitation"
                f"&forecast_days=1"
            )
            weather_resp = await self._http.get(weather_url)
            weather_data = weather_resp.json()

            current = weather_data.get("current", {})
            temp = current.get("temperature_2m", "N/A")
            feels_like = current.get("apparent_temperature", "N/A")
            humidity = current.get("relative_humidity_2m", "N/A")
            wind = current.get("wind_speed_10m", "N/A")
            precip = current.get("precipitation", 0)

            result = (
                f"🌤️ **Weather in {location_name}**\n"
                f"Temperature: {temp}°C (Feels like {feels_like}°C)\n"
                f"Humidity: {humidity}%\n"
                f"Wind: {wind} km/h\n"
                f"Precipitation: {precip} mm\n"
                f"Source: Open-Meteo (real-time)"
            )

            logger.info("Weather data fetched", city=city, location=location_name)
            return result

        except Exception as e:
            logger.error("Weather fetch failed", query=query, error=str(e))
            return None

    async def _get_news(self, query: str) -> str | None:
        """
        Get latest news from NewsData.io (free tier: 200 req/day).
        """
        try:
            url = f"{settings.NEWS_API_URL}?apikey={settings.NEWS_API_KEY}&q={query}&language=en"
            resp = await self._http.get(url)
            data = resp.json()

            articles = data.get("results", [])[:3]
            if not articles:
                return None

            parts = ["📰 **Latest News**\n"]
            for i, article in enumerate(articles, 1):
                title = article.get("title", "No title")
                source = article.get("source_name", "")
                description = (article.get("description") or "")[:200]
                parts.append(f"{i}. **{title}** — {source}\n{description}")

            return "\n\n".join(parts)

        except Exception as e:
            logger.error("News fetch failed", query=query, error=str(e))
            return None

    @staticmethod
    def _is_weather_query(query: str) -> bool:
        """Detect weather-related queries."""
        keywords = ["weather", "mausam", "temperature", "rain", "forecast", "humidity", "wind"]
        return any(k in query for k in keywords)

    @staticmethod
    def _is_news_query(query: str) -> bool:
        """Detect news-related queries."""
        keywords = ["news", "khabar", "latest", "breaking", "today", "headlines"]
        return any(k in query for k in keywords)

    @staticmethod
    def _extract_city(query: str) -> str | None:
        """
        Extract city name from a weather query using simple pattern matching.
        Example: "weather in Karachi" → "Karachi"
        """
        patterns = [
            r"weather\s+in\s+([a-zA-Z\s]+)",
            r"([a-zA-Z\s]+)\s+weather",
            r"mausam\s+(?:of|in)\s+([a-zA-Z\s]+)",
            r"([a-zA-Z\s]+)\s+ka\s+mausam",
        ]
        for pattern in patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._http.aclose()
